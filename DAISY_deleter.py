import json
import os
import pickle
import time
from datetime import datetime
from datetime import timedelta

here = os.getcwd()
client_secret_path = here+r'\client_secret.json'
#b = 12+throwerror
try:
    #print('got here 5')
    with open('service_definition.pkl', 'rb') as f:
        service = pickle.load(f)
except Exception as a:
    print('got here by failing to load service definition')
    print(a)

with open('inpsdict.json', "r") as json_file:
    full_inputs_dict = json.load(json_file)

#for n in ['04']:
for n in full_inputs_dict.keys():

    inputs_dict = full_inputs_dict[n]
    search_terms = inputs_dict['search_terms']
    tz = inputs_dict['tz']
    location = inputs_dict['location']

    print('doing '+str(n))

    calendar_list = service.calendarList().list(pageToken=None).execute()
    for cal in calendar_list['items']:
        if cal['summary'] == f'DAISY{n}':
            dai_id = cal['id']
        elif cal['summary'] == f'DAISY{n} (possibly irrelevant)':
            ir_id = cal['id']
    print(dai_id)
    print(ir_id)

    anydeleted = True
    for id in [dai_id,ir_id]:
        for r in range(1,5):
            if anydeleted: # check that this works right to do dai and ir
                anydeleted = False
                for m in [0,1,-1]:
                    now = datetime.now()
                    month = now.month + m
                    if month == 13:
                        month = 1
                        year = now.year+1
                    elif month == 0:
                        month = 12
                        year = now.year-1
                    else:
                        year = now.year
                    for d in range(1,31):
                        now = datetime.now()

                        timemin = datetime(year,month,d)
                        timemax = timemin+timedelta(days=r)

                        timemin = (timemin.isoformat())+"z"
                        timemax = (timemax.isoformat())+"z"

                        print(timemin+" "+timemax)

                        existing_events = service.events().list(calendarId=id,showDeleted=False,timeMin=timemin,timeMax=timemax,timeZone=tz).execute()['items']

                        existing_events_nid = []
                        for event in existing_events:

                            try:
                                enid = {
                                    'summary':event['summary'],
                                    'description':event['description'],
                                    'start':event['start'],
                                    'end':event['end']
                                    }
                                existing_events_nid.append(enid)
                            except:
                               print(event)

                        for event in sorted(existing_events,key=lambda d: d['summary']):
                            eventid = event['id']
                            try:
                                enid = {
                                    'summary':event['summary'],
                                    'description':event['description'],
                                    'start':event['start'],
                                    'end':event['end']
                                    }
                            except:
                                enid = {
                                'summary':event['summary'],
                                #'description':event['description'],
                                'start':event['start'],
                                'end':event['end']
                                }


                            if abs(((datetime.fromisoformat(event['end']['dateTime'])) - datetime.fromisoformat(event['start']['dateTime'])).days) > 10:
                                service.events().delete(calendarId=id, eventId=eventid).execute()

                            #print("enid summary "+enid['summary'])
                            #{key : val for key, val in event.items() if (key != bad for bad in ['id','etag','htmlLink','created','updated','iCalUID'])}
                            if (existing_events_nid.count(enid) > 1):
                            #if existing_events.count(event) > 1:
                                try:
                                    service.events().delete(calendarId=id, eventId=eventid).execute()
                                    print('dai deleted '+event['summary'])
                                except:
                                    print("fail delete "+event['summary'])

                                existing_events_nid.remove(enid) # supposed to only remove first occurence
                                anydeleted = True
                                #time.sleep(2)
                            else:
                                #print(" ")
                                print('not deleted '+event['summary'])
                                #print(enid)
                        time.sleep(5)
