# for adding events to initial calendar
import os
import json
from datetime import datetime
from datetime import timedelta
import pickle
import time
import traceback

from googleapiclient.errors import HttpError
from DAISYhelpers import check_if_exists
from DAISYhelpers import flag_best
from DAISYhelpers import check_relevance
from DAISYhelpers import build_city_event_pool
from DAISYhelpers import get_city_events_for_user

with open('inpsdict.json', "r") as json_file:
    full_inputs_dict = json.load(json_file)
w = []
for n in full_inputs_dict.keys():
    inp_dict = full_inputs_dict[n]
    try:
        if inp_dict['new'] == "yes":
            w.append(n) # = n
            print("will do "+str(n))
        else:
            print("not do "+str(n))
    except Exception as e:
        print(e)
        print("not do "+str(n))


outs = []

print(w)
#if len(w) == 0:
#    w += "5"
if len(w) > 0:
    #w += "5"
    outs.append("NOW RUNNING DAISY ALWAYS")
    outs.append("NOW RUNNING DAISY ALWAYS")
    outs.append("NOW RUNNING DAISY ALWAYS")
    with open("alwaysresult.txt",'w') as file:
            file.write(str(outs))
    here = os.getcwd()
    client_secret_path = here+r'\client_secret.json'

    try:
        #print('got here 5')
        with open('service_definition.pkl', 'rb') as f:
            service = pickle.load(f)
    except Exception as a:
        outs.append('got here by failing to load service definition')
        outs.append(a)

    city_events = build_city_event_pool(full_inputs_dict, w)

    for n in w:
        full_inputs_dict[n]['timestamp'] = datetime.now().isoformat()
        with open('inpsdict.json', 'w') as json_file:
            json.dump(full_inputs_dict, json_file, indent=4)
        not_added = []
        unimportant_not_added = []
        print(f'beginning {n} for real')

        inputs_dict = full_inputs_dict[n]
        search_terms = inputs_dict['search_terms']
        tz = inputs_dict['tz']
        location = inputs_dict['location']
        try:
            avoid_terms = inputs_dict['avoid_terms']
        except:
            avoid_terms = False
        try:
            block_terms = inputs_dict['block']
        except:
            block_terms = False

        calendar_list = service.calendarList().list(pageToken=None).execute()
        for cal in calendar_list['items']:
            if cal['summary'] == f'DAISY{n}':
                dai_id = cal['id']
            elif cal['summary'] == f'DAISY{n} (possibly irrelevant)':
                ir_id = cal['id']

        # Get events, add them to calendar
        events = get_city_events_for_user(city_events, location)
        print(events)
        for event in events:
            try:
                exists_on_main = check_if_exists(service, event, dai_id,tz)
                exists_on_ir = check_if_exists(service, event, ir_id,tz)
                if exists_on_main or exists_on_ir:
                    continue
                print('checked if exists')
                #event = format_event(event, tz)
                #print('formatted')
                [relevant,show] = check_relevance(event, search_terms, avoid_terms,block_terms)
                print('relevanced')
                # add to calendar or irrelevant event list
                if not show:
                    print(f'not showing {event["summary"]}')
                    continue
                if relevant:
                    useid = dai_id
                else:
                    useid = ir_id
                try:
                    service.events().insert(calendarId=useid, body=event).execute()
                except HttpError as insert_error: # duplicate can occur between check and insert
                    if insert_error.resp.status == 409:
                        continue
                    print("something went wrong adding "+event['summary']+" to calendar")
                    eventstr = str(event['summary'])+"\n"+str(event['description'])
                    if relevant:
                        not_added.append(eventstr)
                    else:
                        unimportant_not_added.append(eventstr)
                except Exception as insert_error: # something went wrong adding to calendar
                    if 'already exists' in str(insert_error).lower():
                        continue
                    print("something went wrong adding "+event['summary']+" to calendar")
                    eventstr = str(event['summary'])+"\n"+str(event['description'])
                    if relevant:
                        not_added.append(eventstr)
                    else:
                        unimportant_not_added.append(eventstr)

            except Exception as exefor:
                print("-"*50)
                print("-"*50)
                print("-"*50)
                try:
                    print("problem formatting \n\n"+str(event)+"\n\n or something, hard to be sure.")
                    print(exefor)
                    print(traceback.format_exc())
                except:
                    pass
                print("-"*50)
                print("-"*50)
                print("-"*50)

        # add notes to calendar as 24-h events
        base_event_dict = {
            'end':{'dateTime':datetime.today().replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(hours=24),'timeZone':tz},
            'start':{'dateTime':datetime.today().replace(hour=0,minute=0,second=0,microsecond=0),'timeZone':tz},
            'summary':'NOTES ON EVENTS NOT ADDED TO CALENDAR'
            }
        notes_real_dict = base_event_dict
        if len(not_added)>0:
            notes_real_dict['Description'] = str("\n\n".join(not_added))
            service.events().insert(calendarId=dai_id, body=notes_real_dict).execute()
        notes_ir_dict = base_event_dict
        if len(unimportant_not_added)>0:
            try:
                notes_ir_dict['Description'] = str("\n\n".join(unimportant_not_added))
                service.events().insert(calendarId=ir_id, body=notes_ir_dict).execute()
            except Exception as exe161:
                print(exe161)
        try:
            flag_best(service,tz,dai_id,search_terms,avoid_terms)
        except:
            pass

        time.sleep(5 * 60)
