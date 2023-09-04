#!/usr/bin/env python
# coding: utf-8

# In[ ]:


import requests
from urllib import parse
from datetime import datetime, timedelta, time
from math import sin
import pandas as pd
import numpy as np
from io import StringIO
import time
import SendReceiveFunctions
import csv
from scipy.interpolate import CubicSpline, interp1d

# Imports required for the multiprocessing
from multiprocessing import Process
from multiprocessing import Queue
from multiprocessing import Lock

queue, lock = SendReceiveFunctions.CommunicationInitialisation()

# Initialising functions for data logging

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
        
def SoC_csv(data):
    with open('SoC_Output.csv', 'a', newline='') as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(data)
        

# Function to calculate current wind output

def Curtailed_power():
    
    # API call current weather
    response=requests.get('http://api.weatherapi.com/v1/current.json?key=453a30c73e744202a5a95548231407&q=55.015170,-4.996922&aqi=no')# Store the response as dataDayAhead variable
    dataCurrentWeather = response.json()
    
    # Sample data points
    x = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21]
    y = [21.3, 84.9, 197.3, 363.8, 594.9, 900.8, 1274.4, 1633.0, 1863.0, 1960.4, 1990.4, 1997.9, 1999.6, 1999.9, 2000, 2000, 2000, 2000, 2000]


    # Create linear interpolation function
    linear_interp = interp1d(x, y, kind='linear')
    
    # Convert from kph
    Wind_ms=dataCurrentWeather['current']['wind_kph']/3.6
    
    # Corret 10m API wind speed to 80m
    WindSpeed_corrected=Wind_ms+0.034*Wind_ms+0.919
    
    # Check if wind speed is before cut-in or after cut-off
    if (WindSpeed_corrected<3 or WindSpeed_corrected>21):
        Power=0
    else:
        Power=linear_interp(WindSpeed_corrected)
    
    string_to_file('Current Wind Power: '+str(Power))

    # There are 12 turbines in the wind farm
    return 12*Power/1000

#This function takes the next day EFA decisions

def Decision_7pm(current_date, Capped_Power,Next_EFA0):
    
    
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
    response2=requests.get('http://api.weatherapi.com/v1/forecast.json?key=453a30c73e744202a5a95548231407&q=55.015170,-4.996922&days=2&aqi=no&alerts=no')
    dataWeather_D0 = response2.json()['forecast']['forecastday'][0]
    dataWeather_D1 = response2.json()['forecast']['forecastday'][1]
    
    # Initialise decision arrays
    
    # Constrained array =1 as default for frequency control
    Constrained_array=np.ones(48)
    
    # Surplus power =0 as default, no surplus power
    Surplus_Power=np.zeros(48)
    
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
            # half hour 47 is half hour 0 etc.
            limit = dataDayAhead[half_hour_index]['Limit (MW)']
            flow = dataDayAhead[half_hour_index]['Flow (MW)']

            # Special case that data is missing but row is still there -> resort to frequency response
            if limit is None or flow is None:
                continue

            # If the limit is reached, store half hour information on constraint, capped power and surplus power
            elif 0.78*float(limit) <= float(flow):
                
                
                PowerOut=power_out(dataDayAhead[half_hour_index]['Date (GMT/BST)'],dataWeather_D1,dataWeather_D0)

                # This if will determine if it is the first contrained half hour. If so it will set the constrained wind output.
                if (Capped_Power==0):
                    Capped_Power=max(PowerOut,0.0000001)
                    # 0.00001 deals with issue that the capped power could be 0 (constrained boundary but no wind) 
                    # but then it also shouldn't be changed again, so 0.00001 makes sure the if isn't satisfied
                
                # Short term management of inconsistency in special case where only data from the previous day is available 
                if(len(dataDayAhead)==2):
                    Constrained_array[0]=1
                    Constrained_array[1]=1
                    if(half_hour_index==0):
                        half_hour_index=47
                    if(half_hour_index==1):
                        half_hour_index=46
                
                # Boundary is constrained at that half hour
                Constrained_array[half_hour_index]=0
                
                # Half hourly information of capped Power
                Power_cap[half_hour_index]=Capped_Power
                    
                Surplus_Power[half_hour_index]=max(PowerOut-Capped_Power,0) 
                # 0 for Case where wind goes down even though boundary is still constrained -> don't want negative surplus

            # If boundary limit is no longer reached, reset the capped power            
            else:
                Capped_Power=0
            
        else:
            print('Missing constraint data for half hour number', half_hour_index+1, 'starting in day', date_string_D0)
            string_to_file('Missing contraint data for half hour '+ str(half_hour_index))
       
    
    # Set output arrays in chronological order to avoid confusion
    Constrained_array = Constrained_array[::-1]
    Surplus_Power = Surplus_Power[::-1]
    Power_cap = Power_cap[::-1]
    
    print(Constrained_array)
    
    # Need to translate half hour information to EFA periods
    
    for half_hour_index in Half_Hours:
        
        if Constrained_array[half_hour_index]==0:
            Surplus_Energy[half_hour_index//8]+=Surplus_Power[half_hour_index]*0.5
            EFA[half_hour_index//8]=0

    # Storing time before and after contraint in EFA period to assess discharge/charge capacity in that EFA period 
    Time_before_curtailment=[0,0,0,0,0,0]
    Time_after_curtailment=[0,0,0,0,0,0]
    
    #How many free half hour periods in the EFA
    Sum_free_periods=[0,0,0,0,0,0]
    
    # Incorporate rule of EFA=2. See dissertation
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
            while Constrained_array[index*8+add_on]==1:
                add_on+=1
                Time_before_curtailment[index]=add_on
                    
            while Constrained_array[(index+1)*8-1-sub_on]==1:
                sub_on+=1
                Time_after_curtailment[index]=sub_on
        
        # Finding number of free half_hours per EFA period
        Sum_free_periods[index]=sum(Constrained_array[index*8:(index+1)*8-1])
    
    # Now making key decisions:
    # If surplus energy will be less than 2MWh, and free periods are less than 2, will need period after to discharge
    # If getting more than 2MWh, and if time after curtailment is less than 1h, then I need a period after to discharge
    # If time before is also less than 1h, I need a period to discharge
    
    for index in range(0,6):
        if EFA[index]==0:
            if Max_Storage/8>Surplus_Energy[index]:
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
    
    string_to_file('Half hour detail'+str(Constrained_array))
    
    return EFA, Capped_Power, Next_EFA0, Constrained_array,Power_cap


# This function predicts the power output 

def power_out(DateTime,DataWeatherD1,DataWeatherD0): 
    
    #Split date and time
    date_string, time_string = DateTime.split('T')
  
    # Convert the time string to a datetime object
    time = datetime.strptime(time_string, '%H:%M:%S').time()
    
    # Round down the minutes to the nearest full hour
    rounded_time = time.replace(minute=0)
    
    # Extract the hour component as an integer
    hour = int(rounded_time.strftime('%H'))

    
    if (hour>=22): #Have to go in day before weather
        WindSpeed=DataWeatherD0['hour'][hour]['wind_kph']/3.6 #m/s
    else:
        WindSpeed=DataWeatherD1['hour'][hour]['wind_kph']/3.6 #m/s
    
    #Converting to 80m wind speed with Hellman exponential law, alpha=0.1
    #WindSpeed80m=WindSpeed*8**0.1
    
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


def Market_Revenue_Function(Market_Array,date):
    
    Market_revenue=0
   
    # Formatting date for API
    dateD1=date
    dateD0=date-timedelta(days=1)
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
        string_to_file('Market Transaction on Settlement period:'+ str(settlement_index)+'Market Price'+str(MarketPriceDF['HDR'][settlement_index]))
                
    return Market_revenue

def FR_Revenue_Function(current_date, EFA):

    # Initialise total revenue
    Total_Revenue=0
    
    # Format date for API to start and end date
    date_string_D0=current_date.strftime('%Y-%m-%dT%H:%M:00.000Z')
    date_string_D1=(current_date+timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:00.000Z')

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


# Necessity to do a lot of initialisations for the code to run before the first decision is taken :

Max_Storage=4
Max_Output=4

# Power at which the turbine is capped when there is constraint, this one allows continuity between days
Next_Capped_Power=0

# To ensure Decision is only called once
Decision_made=0
Pay_made=0

# Continuity over EFAs
Next_EFA0=1

# EFA periods
EFA=[1,1,1,1,1,1] # Essentially for time before first 19:00 kicks in
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

# Get the local time as a time tuple
local_time_tuple = time.localtime()

# Convert the time tuple to a datetime object
local_datetime = datetime(*local_time_tuple[:6])
# Decision function works with time set at 23:00 (start of EFA period)
EFA_start_time = datetime(1,1,1,23, 0, 0).time()
EFA_start_datetime = datetime.combine(local_datetime.date(), EFA_start_time)

Old_SOC=50

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

with open('SoC_Output.csv', 'w', newline='') as csvfile:
    csv_writer = csv.writer(csvfile)
    csv_writer.writerow([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
    csv_writer.writerow(['SoC Updated every 15mins'])

#For market transaction
Curtailing=0
Next_Curtailing=0
    

while True:

    # Get the local time as a time tuple
    local_time_tuple = time.localtime()

    # Convert the time tuple to a datetime object
    local_datetime = datetime(*local_time_tuple[:6])

    #On french time
    local_datetime=local_datetime

    # Building 6pm decision time
    Decision_time = datetime(1,1,1,19, 13, 0).time()
    Decision_datetime = datetime.combine(local_datetime.date(), Decision_time)

    if local_datetime == Decision_datetime and Decision_made==0:

        # Go through decision once
        Decision_made=1

        # Decision function works with time set at 23:00 (start of EFA period)
        EFA_start_time = datetime(1,1,1,23, 0, 0).time()
        EFA_start_datetime = datetime.combine(local_datetime.date(), EFA_start_time)
        
        # Update continuity capped power
        Capped_Power=Next_Capped_Power

        # Make decision
        NewEFA, Next_Capped_Power, Next_EFA0, New_Constrained_array, New_Power_cap=Decision_7pm(EFA_start_datetime, Capped_Power,Next_EFA0)
        
        # Decision is made at 7pm but EFA period is 23:00 - 23:00. Need to do some assembly work on arrays
        EFA[0:5]=NewEFA[0:5]
        EFA[5]=OldEFA[5]
        EFA=NewEFA
        
        Constrained_array[0:40]=New_Constrained_array[0:40]
        Constrained_array[40:48]=Old_Constrained_array[40:48]
        Old_Constrained_array=New_Constrained_array
        
        Power_cap[0:40]=New_Power_cap[0:40]
        Power_cap[40:48]=Old_Power_cap[40:48]
        Old_Power_cap=New_Power_cap
        
    
        
       
    
    Pay_time = datetime(1,1,1,23,0, 0).time()
    Pay_datetime = datetime.combine(local_datetime.date(), Pay_time)
    
    if local_datetime== Pay_datetime and Pay_made==0:
        
        Pay_made=1
        # Market Money between 23:00 and 23:00 D+1
        Market_Revenue=Market_Revenue_Function(Market_array,local_datetime)

        Market_array=[]
        
        # FR Revenue
        print('\nMarket revenue for the day:', Market_Revenue,'\n')
    
        FR_Revenue= FR_Revenue_Function(local_datetime, OldEFA)
        
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
    efa_period_duration = 4  # hours
    efa_period_index = (time_diff // timedelta(hours=efa_period_duration))%6  #%6 is there if i'm just testing
    
    
    # Same to get half hour index
    half_hour_duration=0.5
    half_hour_index=(time_diff//timedelta(hours=half_hour_duration))%48
    
    # And same to update battery commands every 15mins
    quarter_hour_duration=0.25
    quarter_hour_index=(time_diff//timedelta(hours=quarter_hour_duration))%96
    
    
    #Update every 15mins
    if not quarter_hour_index==old_quarter_hour_index:
        
        
        print('efa period:', efa_period_index)
        
        print('EFA period:', efa_period_index)
        string_to_file('EFA period: ' +str(efa_period_index))
        
        time.sleep(3)
        
        with lock['Oxford']:
            DataReceived = queue['Oxford'].get()
        
        SOC=DataReceived['SOC']

        SoC_csv([SOC])
        
        time.sleep(3)
        
            
        if EFA[efa_period_index]==1 or EFA[efa_period_index]==2:
            
        
            Power_out=999999999
            SendReceiveFunctions.SendPowers('Oxford',Power_out,0,1200)
            print('Currently doing frequency control')
            
            string_to_file('Frequency Control, EFA=1 or 2')
                
            Curtailing=0
        
        
        
        elif EFA[efa_period_index]==0:
            
            if Constrained_array[half_hour_index]==0:
                Power_out=-max(0,Curtailed_power()-Power_cap[half_hour_index])*1000
                SendReceiveFunctions.SendPowers('Oxford',Power_out,0,1200)
                
                string_to_file('Curtailment, Power out =' +str(Power_out))
                
                Wind_Power_csv([local_datetime.strftime("%Y-%m-%d %H:%M:%S")])
                Wind_Power_csv([Curtailed_power])
                Wind_Power_csv([Power_cap[half_hour_index]])
                
                # So that market transaction isn't counted
                Curtailing+=1
                
                    
            elif SOC>25:

                Battery_level=(SOC/100)*Max_Storage
                Power_out=(Battery_level-Max_Storage/2)*1000/0.25 #kw
                SendReceiveFunctions.SendPowers('Oxford',Power_out,0,1200)
                
                string_to_file('No constraint, power out= '+str(Power_out))
                
                Curtailing=0
                
        elif EFA[efa_period_index]==3:
            Power_out=4000 #kw assuming if its at lowest SOC it rejects this command
            print('Im at EFA=3, so emptying battery')
            
            string_to_file('EFA=3, power out = '+str(Power_out))
            
            Curtailing=0
            
            
        
        elif EFA[efa_period_index]==4:

            Battery_level=(SOC/100)*Max_Storage
            Power_out=(Battery_level-Max_Storage/2)*1000/0.25 #kw
            SendReceiveFunctions.SendPowers('Oxford',Power_out,0,1200)
            
            string_to_file('EFA = 4, power out =' + str(Power_out))
            
            Curtailing=0
        
        # Every 30mins save the Energy transaction
        
        if quarter_hour_index%2==0:
            
            if Curtailing<=1 and Next_Curtailing==0:
                Energy_difference=Max_Storage*(Old_SOC-SOC)/100 # positive if sent to the grid
                Market_array.append([half_hour_index,Energy_difference])
                string_to_file('Market transaction at half hour index '+str(half_hour_index)+' Energy difference is '+ str(Energy_difference)+'MWh')
            
            # This one is for the last curtailing half hour
            Next_Curtailing=0
            
            if Curtailing>=1:
                Next_Curtailing=1
            
            Old_SOC=SOC
           
              
            
        
        # To ensure the loop doesn't go right back into Decision
        time.sleep(1)
        Decision_made=0
        Pay_made=0
    
    time.sleep(0.1)
    old_quarter_hour_index=quarter_hour_index

