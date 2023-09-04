#!/usr/bin/env python
# coding: utf-8

# In[203]:


import requests
from urllib import parse
from datetime import datetime, timedelta, time
from math import sin
import pandas as pd
import numpy as np
from io import StringIO
import time
#import SendReceiveFunctions
import csv
from scipy.interpolate import CubicSpline, interp1d

# In real codes other imports for battery model



start_datetime=datetime(2023,3,25,0,0,0)
end_datetime=datetime(2023,3,26,23,0,0)
    
local_datetime=start_datetime

# Decision function works with time set at 23:00 (start of EFA period)
EFA_start_time = datetime(1,1,1,23, 0, 0).time()
EFA_start_datetime = datetime.combine(local_datetime.date(), EFA_start_time)

def string_to_file(data):
    with open("output.txt", "a") as file:
        file.write(data + "\n")
        
def FR_Revenue_csv(data):
    with open('FR_Revenue_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        
def Market_Revenue_csv(data):
    with open('Market_Revenue_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        
def Wind_Power_csv(data):
    with open('Wind_Power_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        
def Wind_Power_csv2(data):
    with open('Wind_Power_Output2.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        
def Wind_Curtailed_csv(data):
    with open('Wind_Curtailed_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)

def Wind_Saved_csv(data):
    with open('Wind_Saved_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        
def SoC_csv(data):
    with open('SoC_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)

Max_Storage=28.8
Battery_level=Max_Storage/2
Old_Battery_level=Battery_level
Max_Output=Max_Storage
Total_curtailed_energy=0

# Necessity to do a lot of initialisations for the code to run before the first decision is taken :

# Power at which the turbine is capped when there is constraint, this one allows continuity between days
Next_Capped_Power=0

# To ensure Decision is only called once
Decision_made=0
Pay_made=0

# Continuity over EFAs
Next_EFA0=1

# EFA periods
EFA=[1,1,1,1,1,1] # Essentially for time before first 18:00 kicks in
OldEFA=EFA

# Half hour power caps
Power_cap=np.zeros(48)
Old_Power_cap=Power_cap

# Half hour constraint information
Constrained_array=np.ones(48)
Old_Constrained_array=Constrained_array

# Updating battery commands every quarter hour
old_quarter_hour_index=-1

# Store transactions

Market_array=[]


# Another initialisation to set EFA_start_datetime before the decision time




with open("output.txt", "w") as file:  # Open in write mode to clear the file
    file.write('Code launched at time'+local_datetime.strftime("%Y-%m-%d %H:%M:%S")+'\n')

with open('FR_Revenue_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])

with open('Market_Revenue_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    
with open('Wind_Power_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    
with open('Wind_Power_Output2.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    
with open('Wind_Curtailed_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    
with open('Wind_Saved_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])

with open('SoC_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    csv_writer.writerow(['SoC Updated every 15mins'])

# To manage issues with  market transactions while curtailing
Curtailing=0
Curtailing2=0
Done_FR=0



    
while True:



    local_datetime=local_datetime+timedelta(seconds=1)


    if local_datetime>end_datetime:
        break

    if not local_datetime.month==old_month:
        name='fnew-2023-'+str(local_datetime.month)+'.csv'


        frequencyDF=pd.read_csv(name)
        old_month=local_datetime.month


    # Building 6pm decision time
    Decision_time = datetime(1,1,1,19, 0, 0).time()
    Decision_datetime = datetime.combine(local_datetime.date(), Decision_time)

    if Decision_datetime<=local_datetime < Decision_datetime+timedelta(seconds=3) and Decision_made==0:


        # Go through decision once
        Decision_made=1
        Pay_made=0

        # Decision function works with time set at 23:00 (start of EFA period)
        EFA_start_time = datetime(1,1,1,23, 0, 0).time()
        EFA_start_datetime = datetime.combine(local_datetime.date(), EFA_start_time)

        # Update continuity capped power
        Capped_Power=Next_Capped_Power
        
        # Make decision
        NewEFA, Next_Capped_Power, Next_EFA0, New_Constrained_array, New_Power_cap,dataWeatherD0,dataWeatherD1,Total_curtailed_energy_daily,Total_wind_energy_daily, Last_EFA2=Decision_6pm(EFA_start_datetime, Capped_Power,Next_EFA0, Last_EFA)

        Last_EFA=Last_EFA2
        # Decision is made at 7pm but EFA period is 23:00 - 23:00. Need to do some assembly work on arrays
        EFA[0:5]=NewEFA[0:5]
        EFA[5]=OldEFA[5]
      


        Constrained_array[0:40]=New_Constrained_array[0:40]
        Constrained_array[40:48]=Old_Constrained_array[40:48]
        Old_Constrained_array=New_Constrained_array

        Power_cap[0:40]=New_Power_cap[0:40]
        Power_cap[40:48]=Old_Power_cap[40:48]
        Old_Power_cap=New_Power_cap

        string_to_file('Constrained array '+ str(Constrained_array))
    


    Pay_time = datetime(1,1,1,23,0, 0).time()
    Pay_datetime = datetime.combine(local_datetime.date(), Pay_time)

    if Pay_datetime<=local_datetime< Pay_datetime+timedelta(seconds=3) and Pay_made==0:

        Pay_made=1
        Decision_made=0
        # Market Money between 23:00 and 23:00 D+1
        Market_Revenue=Market_Revenue_Function(Market_array)
            
        Market_Revenue_total+=Market_Revenue

        Market_array=[]

        # FR Revenue
        print('\nMarket revenue for the day:', Market_Revenue,'\n')

        FR_Revenue= FR_Revenue_Function(local_datetime, OldEFA)
            
        FR_Revenue_total+=FR_Revenue

        # so that FR revenue is the past day
        OldEFA=NewEFA

        string_to_file('Market Revenue for the day: '+ str(Market_Revenue))
        string_to_file('FR Revenue for the day: ' + str(FR_Revenue))

        Market_Revenue_csv([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
        Market_Revenue_csv([Market_Revenue])

        FR_Revenue_csv([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
        FR_Revenue_csv([FR_Revenue])


    # Calculate the difference between current time and EFA start time
    time_diff = local_datetime - EFA_start_datetime

    # Calculate the EFA index based on the time difference and EFA period duration (4 hours)
    efa_period_duration = 4  # seconds
    efa_period_index = (time_diff // timedelta(hours=efa_period_duration))%6  #%6 is there if i'm just testing

    # Same to get half hour index
    half_hour_duration=0.5 # seconds
    half_hour_index=(time_diff//timedelta(hours=half_hour_duration))%48

    # And same to update battery commands every 15mins
    quarter_hour_duration=0.25 #seconds
    quarter_hour_index=(time_diff//timedelta(hours=quarter_hour_duration))


    #Update every 15mins
    if not quarter_hour_index==old_quarter_hour_index:

        print('EFA period:', efa_period_index)
        string_to_file('EFA period: ' +str(efa_period_index))
        

        SoC_csv([Battery_level])


        if EFA[efa_period_index]==1 or EFA[efa_period_index]==2:

            string_to_file('Frequency Control, EFA=1 or 2')
            Curtailing=0

            end_time=local_datetime+timedelta(hours=4)
            start_of_month = datetime(local_datetime.year, local_datetime.month, 1,0,0,0)
            end_time=datetime.combine(local_datetime.date(), datetime(1,1,1,4*efa_period_index+3,0, 0).time())
            if(local_datetime.hour>=23):
                end_time=datetime.combine((local_datetime+timedelta(days=1)).date(), datetime(1,1,1,4*efa_period_index+3,0, 0).time())

            while local_datetime<end_time:

                #Calculate the index
                index = (local_datetime - start_of_month).total_seconds()+1
                frequency=(frequencyDF['f'][index])

                #Calculate power delivered in that second with frequency control
                power=DCH_DCL(frequency)
                Battery_level+=power/3600
                
                if(index)%900==0:
                    SoC_csv([Battery_level])

                if(index)%1800==0:

                    time_diff = local_datetime - EFA_start_datetime
                    half_hour_index=(time_diff//timedelta(hours=half_hour_duration))%48

                    Energy_difference=Old_Battery_level-Battery_level

                    Market_array.append([half_hour_index,Energy_difference])
                    Old_Battery_level=Battery_level


                    string_to_file('Market transaction at half hour index '+str(half_hour_index)+' Energy difference is '+ str(Energy_difference)+'MWh')
                
                Done_FR=1
                    
                local_datetime+=timedelta(seconds=1)



        elif EFA[efa_period_index]==0:

            if Constrained_array[half_hour_index]==0:

                date_string = local_datetime.strftime('%Y-%m-%dT%H:%M:%S')

                Power_out=-max(0,power_out(date_string,dataWeatherD1,dataWeatherD0)-Power_cap[half_hour_index])
                Energy_diff=-Power_out*0.25       

                Battery_level=min(Max_Storage,Battery_level+Energy_diff)
             

                string_to_file('Curtailment, Power out =' +str(Power_out))
 

                Curtailing=1
                Curtailing2=1

        



            elif Battery_level>1:


                Power_out=-max(-Max_Output,min(Max_Output,(Battery_level-0)/0.25))
                Energy_diff=Power_out*0.25
                Battery_level+=Energy_diff

                string_to_file('No constraint, power out= '+str(Power_out))
                Curtailing=0


        elif EFA[efa_period_index]==3:

            Power_out=-Max_Output
            Energy_diff=Power_out*0.25
            Battery_level+=Energy_diff

            Curtailing=0

            if Battery_level<0:
                Battery_level=0

            print('EFA=3, battery level is:', Battery_level)
            string_to_file('EFA=3, power out = '+str(Power_out))

        elif EFA[efa_period_index]==4:

            Power_out=-max(-Max_Output,min(Max_Output,(Battery_level-Max_Storage/2)/0.25))
            Energy_diff=Power_out*0.25
            Battery_level+=Energy_diff

            Curtailing=0

            print('EFA=4, battery level is:', Battery_level)

            string_to_file('EFA = 4, power out =' + str(Power_out))

        # Every 30mins save the Energy transaction

        if quarter_hour_index%2==1 and Done_FR==0:

            if Curtailing==0:
                Energy_difference=Old_Battery_level-Battery_level
                Market_array.append([half_hour_index+1,Energy_difference])
                string_to_file('Market transaction at half hour index '+str(half_hour_index+1)+' Energy difference is '+ str(Energy_difference)+'MWh')



        Old_Battery_level=Battery_level




        # To ensure the loop doesn't go right back into Decision
        Done_FR=0

    old_quarter_hour_index=quarter_hour_index


# In[200]:


# Main body, code run at 6pm to decide on action to take during EFAs

def Decision_6pm(current_date, Capped_Power,Next_EFA0,Last_EFA):
    
    print('Making EFA decision for period ', current_date, ' to ', (current_date+timedelta(days=1)),'... \n')
    string_to_file('\nMaking EFA decision for date '+ current_date.strftime("%Y-%m-%d %H:%M:%S"))

    # Some initialising
    is_within_interval=False
    
    # List to loop through half hours. In constraints,47 is the first chronological half hour (23:00 on D+0)
    Half_Hours=range(47,-1,-1)

    # Format day D+0 and D+1 to call APIs succesfully
    date_string_D0=current_date.strftime("%Y-%m-%d")
    date_string_D1=(current_date+timedelta(days=1)).strftime("%Y-%m-%d")

    # Asking data for the FFR decision period which is 23:00 D+0 and 23:00 D+!
    sql_query =  f'''SELECT COUNT(*) OVER () AS _count, * FROM "38a18ec1-9e40-465d-93fb-301e80fd1352" WHERE "Constraint Group" = 'SSHARN' AND "Date (GMT/BST)">= '{date_string_D0}T23:00:00' AND "Date (GMT/BST)" < '{date_string_D1}T23:00:00' ORDER BY "_id" DESC LIMIT 48'''
    params = {'sql': sql_query}

    # Call the API and store response for selected 24h
    response = requests.get('https://api.nationalgrideso.com/api/3/action/datastore_search_sql', params = parse.urlencode(params))
    dataDayAhead = response.json()['result']['records']
    
    # Treat the case where they named SSHARN boundary SHARN, could happen again
    if(len(dataDayAhead)==0):
        
        # Asking data for the FFR decision period which is 23:00 D+0 and 23:00 D+!
        sql_query =  f'''SELECT COUNT(*) OVER () AS _count, * FROM "38a18ec1-9e40-465d-93fb-301e80fd1352" WHERE "Constraint Group" = 'SHARN' AND "Date (GMT/BST)">= '{date_string_D0}T23:00:00' AND "Date (GMT/BST)" < '{date_string_D1}T23:00:00' ORDER BY "_id" DESC LIMIT 48'''
        params = {'sql': sql_query}
        
        # Call the API and store response for selected 24h
        response = requests.get('https://api.nationalgrideso.com/api/3/action/datastore_search_sql', params = parse.urlencode(params))
        dataDayAhead = response.json()['result']['records']
    

    #Weather API for 2 days.
    #Weather API for D+1. json gives info for a whole day
    response2=requests.get(f'http://api.weatherapi.com/v1/history.json?key=7d87e9582d1b426f858213600232808&q=55.015170,-4.996922&dt={date_string_D1}')
    dataWeather_D1 = response2.json()['forecast']['forecastday'][-1]

    #Weather API for D+0.
    response3=requests.get(f'http://api.weatherapi.com/v1/history.json?key=7d87e9582d1b426f858213600232808&q=55.015170,-4.996922&dt={date_string_D0}')
    dataWeather_D0 = response3.json()['forecast']['forecastday'][-1]
    
    # Initialise decision arrays
    
    # Constrained array =1 as default for frequency control
    Constrained_array_local=np.ones(48)
    
    # Surplus power =0 as default, no surplus power
    Surplus_Power=np.zeros(48)
    
    Wind_Power=np.zeros(48)
    
    # Power cap =0 as default, no capped power
    Power_cap=np.zeros(48)
    
    # EFA decisions 1 as default
    EFA = [1, 1, 1, 1, 1, 1]
    
    Current_Next_EFA0=Next_EFA0
        
    # reinitialise
    Next_EFA0=1
    
    # Store surplus energy in case of curtailment (EFA[i]=0)
    Surplus_Energy= [0, 0, 0, 0, 0, 0]


    # Loop over half hours in constraint
    for half_hour_index in Half_Hours:
        
        # Treat the case of missing data therefore dataDayAhead could be empty or smaller, in that case EFA=1
        if(len(dataDayAhead)>half_hour_index):
                    
        
            # Store limit and flow values for the specific half hour
            limit = dataDayAhead[half_hour_index]['Limit (MW)']
            flow = dataDayAhead[half_hour_index]['Flow (MW)']

            # Special case that data is missing but row is still there -> resort to frequency response
            if limit is None or flow is None:
                continue

            # If the limit is reached, store half hour information on constraint, capped power and surplus power
            elif 0.78*float(limit) <= float(flow):
                
            

                # This if will determine if it is the first contrained half hour. If so it will set the constrained wind output.
                if (Capped_Power==0):
                    Capped_Power=max(power_out(dataDayAhead[half_hour_index]['Date (GMT/BST)'],dataWeather_D1,dataWeather_D0),0.0000001)
                    # 0.00001 deals with issue that the capped power could be 0 (constrained boundary but no wind) 
                    # but then it also shouldn't be changed again, so 0.00001 makes sure the if isn't satisfied
                
                half_hour_index2=half_hour_index
                if(len(dataDayAhead)==2):
                    Constrained_array_local[0]=1
                    Constrained_array_local[1]=1
                    if(half_hour_index==0):
                        half_hour_index2=47
                    if(half_hour_index==1):
                        half_hour_index2=46
                        
                # Boundary is constrained at that half hour
                Constrained_array_local[half_hour_index2]=0
                
                # Half hourly information of capped Power
                Power_cap[half_hour_index2]=Capped_Power
                    
                Surplus_Power[half_hour_index2]=max(power_out(dataDayAhead[half_hour_index]['Date (GMT/BST)'],dataWeather_D1,dataWeather_D0)-Capped_Power,0) 
                # 0 for Case where wind goes down even though boundary is still constrained -> don't want negative surplus

            # If boundary limit is no longer reached, reset the capped power            
            else:
                Capped_Power=0
                
            Wind_Power[half_hour_index]=power_out(dataDayAhead[half_hour_index]['Date (GMT/BST)'],dataWeather_D1,dataWeather_D0)

            
        else:
            print('Missing constraint data for half hour number', half_hour_index+1, 'starting in day', date_string_D0)
            string_to_file('Missing contraint data for half hour '+ str(half_hour_index))
       
    
    # Set output arrays in chronological order to avoid confusion
    Constrained_array_local = Constrained_array_local[::-1]
    Surplus_Power = Surplus_Power[::-1]
    Power_cap = Power_cap[::-1]
    
    
    print(Constrained_array_local)
    
    # Need to translate half hour information to EFA periods
    
    for half_hour_index in Half_Hours:
        
        if Constrained_array_local[half_hour_index]==0:
            Surplus_Energy[half_hour_index//8]+=Surplus_Power[half_hour_index]*0.5
            EFA[half_hour_index//8]=0
    
    Total_curtailed_energy=sum(Surplus_Energy)
    
    Total_wind_energy_daily=sum(Wind_Power)*0.5

    # Storing time before and after contraint in EFA period to assess discharge/charge capacity in that EFA period 
    Time_before_curtailment=[0,0,0,0,0,0]
    Time_after_curtailment=[0,0,0,0,0,0]
    
    #How many free half hour periods in the EFA
    Sum_free_periods=[0,0,0,0,0,0]
    
    if Surplus_Energy[0]<Max_Storage/4.7 and EFA[0]==0 and (Last_EFA==1 or Last_EFA==2):
        EFA[0]=2
        
    for index in range(1,6):
        
        # Checking if it's worth to do curtailment
        if Surplus_Energy[index]<Max_Storage/4.7 and EFA[index]==0 and (EFA[index-1]==1 or EFA[index-1]==2):
            # EFA=2 means FR but cannot substantially charge or discharge battery as boundary is constrained
            EFA[index]=2
        
        # finding number of unconstrained half hours before and after curtailment 
        add_on=0
        sub_on=0
        if EFA[index]==0 or EFA[index]==2:
            while Constrained_array_local[index*8+add_on]==1:
                add_on+=1
                Time_before_curtailment[index]=add_on
                    
            while Constrained_array_local[(index+1)*8-1-sub_on]==1:
                sub_on+=1
                Time_after_curtailment[index]=sub_on
        
        # Finding number of free half_hours per EFA period
        Sum_free_periods[index]=sum(Constrained_array_local[index*8:(index+1)*8-1])
    
    # Now making key decisions:
    # If surplus energy will be less than 2MWh, and free periods are less than 2, will need period after to discharge
    # If getting more than 2MWh, and if time after curtailment is less than 1h, then I need a period after to discharge
    # If time before is also less than 1h, I need a period to discharge
    
    for index in range(0,6):
        if EFA[index]==0:
            if Surplus_Energy[index]<Max_Storage/4.7:
                continue
            elif Surplus_Energy[index]<Max_Storage/2:
                if Sum_free_periods[index]<2:
                    # I am getting between 0.5 and 2MWh but I only have 0 or 1 free period so need another EFA after to discharge
                    if index<5:
                         if EFA[index+1]==1: # otherwise you could be constrained anyway
                            EFA[index+1]=4
                    else:
                        Next_EFA0=4
            else:
                if Time_after_curtailment[index]<2:
                    # I am getting over 2MWh but no time do discharge to 2MWh after so need EFA to discharge
                    if index<5:
                        if EFA[index+1]==1:
                            EFA[index+1]=4
                    else:
                        Next_EFA0=4
                if Time_before_curtailment[index]<2:
                    # Need an EFA before to discharge
                    if index>0 and EFA[index-1]==1:
                        EFA[index-1]=3
                        
    # If first EFA has been requested to 4, set it. Except if EFA=0 or 2 in which case boundary is constrained and needed to pass on
    
    if Current_Next_EFA0==4:
        
        index=0
        while (EFA[index]==0 or EFA[index]==2):
            index+=1
            if index==6:
                break
        if index<6:
            EFA[index]=4
        else:
            Next_EFA0=4
    

            
    print('\nEFA results:',EFA)
    print('Surplus Energy results:',Surplus_Energy,'\n')
    
    print('Time before curtailment:', Time_before_curtailment)
    print('Time after curtailment:', Time_after_curtailment,'\n')
    
    string_to_file('\n EFA results: ' +str(EFA))
    string_to_file('Surplus Energy results:'+ str(Surplus_Energy)+'\n')
    
    string_to_file('Half hour detail'+str(Constrained_array_local))
    
    Last_EFA=EFA[5]
    
    
    
    return EFA, Capped_Power, Next_EFA0, Constrained_array_local,Power_cap,dataWeather_D0, dataWeather_D1,Total_curtailed_energy, Total_wind_energy_daily,Last_EFA
    


# In[51]:


# Function taking weather data and time and giving out the corresponding windfarm power. 
# This is for a 2 MW turbine in Glen App wind farm

# DataWeatherD = weather data for D+0
# DataWeather D_1 = weather data for D-1

def power_out(DateTime,DataWeatherD1,DataWeatherD0): 
    
    #Split date and time
    date_string, time_string = DateTime.split('T')
  
    # Convert the time string to a datetime object
    time = datetime.strptime(time_string, '%H:%M:%S').time()
    
    # Round down the minutes to the nearest full hour
    rounded_time = time.replace(minute=0)
    
    # Extract the hour component as an integer
    hour = int(rounded_time.strftime('%H'))
    
    if (hour>=23): #Have to go in day before weather
        WindSpeed=DataWeatherD0['hour'][hour]['wind_kph']/3.6 #m/s
    else:
        WindSpeed=DataWeatherD1['hour'][hour]['wind_kph']/3.6 #m/s
    
    
    WindSpeed_corrected=WindSpeed+0.034*WindSpeed+0.919
    
    # Sample data points
    x = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
    y = [21.3, 84.9, 197.3, 363.8, 594.9, 900.8, 1274.4, 1633.0, 1863.0, 1960.4, 1990.4, 1997.9, 1999.6, 1999.9, 2000, 2000, 2000, 2000, 2000]

    # Create linear interpolation function
    linear_interp = interp1d(x, y, kind='linear')
    
    # Check if wind speed is before cut-in or after cut-off
    if (WindSpeed_corrected<3 or WindSpeed_corrected>21):
        Power=0
    else:
        #Curve fitting with sine sum of power curve given by datasheet. This is where it is based on 2MW turbine
        Power=linear_interp(WindSpeed_corrected)
    
    return 12*Power/1000 #MW, and 12x for a 24MW wind farm
       


# In[52]:


def DCH_DCL(frequency):
    Deadband_Low=49.985 #Hz
    Deadband_High=50.015
    Inflection_Low=49.8 #Hz
    Inflection_High=50.2
    Min_Low=49.5 #Hz
    Max_High=50.5
    
    if Deadband_Low<frequency<Deadband_High:
        output_power=0
    elif Inflection_Low<frequency<=Deadband_Low:
        output_power=((Deadband_Low-frequency)/(Deadband_Low-Inflection_Low))*0.05*Max_Output
    elif Min_Low<=frequency<=Inflection_Low:
        output_power=((Inflection_Low-frequency)/(Inflection_Low-Min_Low))*Max_Output*0.95+0.05
    elif Deadband_High<=frequency<Inflection_High:
        output_power=-((frequency-Deadband_High)/(Inflection_High-Deadband_High))*0.05*Max_Output
    elif Inflection_High<=frequency<=Max_High:
        output_power=-(((frequency-Inflection_High)/(Max_High-Inflection_High))*Max_Output*0.95+0.05)
    
    
    return output_power


# In[70]:


def Market_Revenue_Function(Market_Array):
    
    Market_revenue=0
   
    # Formatting date for API
    dateD1=local_datetime.date()
    dateD0=dateD1-timedelta(days=1)
    date_stringD0=dateD0.strftime("%Y-%m-%d")
    date_stringD1=dateD1.strftime("%Y-%m-%d")
        
    # API call and csv to dataframe
    urlMarket = f'https://api.bmreports.com/BMRS/MID/v1?APIKey=hd4625s7qyrfoxd&FromSettlementDate={date_stringD0}&ToSettlementDate={date_stringD1}&Period=*&ServiceType=csv'
    response_Market = requests.get(urlMarket)
    csv_data = response_Market.text
    MarketPriceDF = pd.read_csv(StringIO(csv_data))
 
    # Loop over every transaction    
    for row in Market_Array:
        settlement_index=row[0]+46 # to get onto next day
        # Calculate revenue = price x volume. Can be negative
        Market_revenue+=MarketPriceDF['HDR'][settlement_index]*row[1] # price*volume
        #print('Transaction occured on Settlement Period:', settlement_index+1, ' Market Price:', MarketPriceDF['HDR'][settlement_index], ' Volume:',row[1])
        string_to_file('Market Transaction on Settlement period:'+ str(settlement_index)+'Market Price'+str(MarketPriceDF['HDR'][settlement_index]) + ' volume:'+str(row[1])+ '\n'+'price:'+str(MarketPriceDF['HDR'][settlement_index]*row[1]))
                
    return Market_revenue


# In[77]:


# Calculates revenue from frequency control DCH and DCL
def FR_Revenue_Function(current_date, EFA):

    # Initialise total revenue
    Total_Revenue=0
    
    # Format date for API to start and end date
    date_string_D0=(current_date-timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:00.000Z')
    date_string_D1=current_date.strftime('%Y-%m-%dT%H:%M:00.000Z')

    # Set up API for both DCL and DCH data
    sql_queryDCH =  f'''SELECT COUNT(*) OVER () AS _count, * FROM "888e5029-f786-41d2-bc15-cbfd1d285e96" WHERE "Service" = 'DCH' AND "EFA Date" >= '{date_string_D0}' AND "EFA Date" < '{date_string_D1}' ORDER BY "_id" ASC LIMIT 6'''
    paramsDCH = {'sql': sql_queryDCH}
    sql_queryDCL =  f'''SELECT COUNT(*) OVER () AS _count, * FROM "888e5029-f786-41d2-bc15-cbfd1d285e96" WHERE "Service" = 'DCL' AND "EFA Date" >= '{date_string_D0}' AND "EFA Date" < '{date_string_D1}' ORDER BY "_id" ASC LIMIT 6'''
    paramsDCL = {'sql': sql_queryDCL}

    
    # Call the APIs
    responseDCH = requests.get('https://api.nationalgrideso.com/api/3/action/datastore_search_sql', params = parse.urlencode(paramsDCH))
    responseDCL = requests.get('https://api.nationalgrideso.com/api/3/action/datastore_search_sql', params = parse.urlencode(paramsDCL))
    
    # Store the response
    dataDCH_Revenue = responseDCH.json()['result']['records']
    dataDCL_Revenue = responseDCL.json()['result']['records']

    # Loop over EFA periods
    for index in range(6):
        
        print('EFA number', index+1,'DCH revenue is', dataDCH_Revenue[index]['Clearing Price'],
               '/h/MW, DCL revenue is', dataDCL_Revenue[index]['Clearing Price'],'/h/MW')
        string_to_file('DCH Revenue: '+ str(dataDCH_Revenue[index]['Clearing Price'])+'DCL Revenue'+str(dataDCL_Revenue[index]['Clearing Price']))
       
        # EFA[index]=0 if curtailment. 4 hours. 4 MW max output.
        if EFA[index]==1 or EFA[index]==2:
            DCH_Revenue=Max_Output*4*float(dataDCH_Revenue[index]['Clearing Price'])
            DCL_Revenue=Max_Output*4*float(dataDCL_Revenue[index]['Clearing Price'])

        else:
            DCH_Revenue=0
            DCL_Revenue=0
            
        
        Total_Revenue+=DCH_Revenue+DCL_Revenue
        
    return Total_Revenue

