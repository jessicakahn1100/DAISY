import json
from datetime import datetime
from datetime import timedelta
import os
import pickle
import time
import traceback

from DAISYhelpers import get_events
#from DAISYhelpers import format_event
from DAISYhelpers import check_if_exists
#rom DAISYhelpers import ask_GPT
from DAISYhelpers import flag_best
from DAISYhelpers import check_relevance

here = os.getcwd()
client_secret_path = here+r'\client_secret.json'
#thro = 5+b
try:
    #print('got here 5')
    with open('service_definition.pkl', 'rb') as f:
        service = pickle.load(f)
except Exception as a:
    print('got here by failing to load service definition')
    print(a)

with open('inpsdict.json', "r") as json_file:
    full_inputs_dict = json.load(json_file)

# Iterate over child dicts
for key, child_dict in full_inputs_dict.items():
    if 'timestamp' in child_dict:
        child_dict['timestamp'] =  datetime.fromisoformat(child_dict['timestamp'])
    else:        # If no timestamp is stored, assign current datetime
        child_dict['timestamp'] = datetime.now()
    if 'new' in child_dict:
        if child_dict['new'] == 'yes':
            child_dict['new'] = 'no'

# Sort parent dictionary keys based on timestamp in child dicts
sorted_keys = sorted(full_inputs_dict.keys(), key=lambda x: full_inputs_dict[x].get('timestamp', datetime.now()))
print(sorted_keys)
# {"1": {"search_terms": ["skating", "crafts", "art", "festivals", "fairs", "queer community", "Pride events", "jewish community", "comedy", "musicals", "parties", "invasive plant cleanup", "board games"], "tz": "America/New_York", "location": ["us", "in", "indianapolis"], "avoid_terms": ["for kids", "for couples", "about Christianity", "like job fairs", "afro"], "new": "no"}, "7": {"search_terms": ["skating", "crafts", "art", "festivals", "fairs", "queer community", "Pride events", "jewish community", "comedy", "musicals", "parties", "invasive plant cleanup", "board games"], "tz": "America/Chicago", "location": ["us", "il", "chicago"], "avoid_terms": ["for kids", "for couples", "about Christianity", "church", "like job fairs", "afro"], "new": "no"}, "3": {"search_terms": ["cats", "EDM", "hiking"], "tz": "America/Los_Angeles", "location": ["us", "il", "san fransisco"], "avoid_terms": ["for kids", "for couples", "about Christianity", "church", "like job fairs", "afro"], "new": "no"}, "5": {"search_terms": ["biking", "cycling", "3D printing", "art", "crafts", "writing", "screenplay", "astronomy", "stars", "board games", "video games", "makerspace", "community service", "make friends", "meet people", "cats"], "tz": "America/Chicago", "location": ["us", "il", "chicago"], "avoid_terms": ["for kids", "for couples", "about Christianity", "like job fairs", "afro", "queer community", "gay"], "new": "no"}}
for key, child_dict in full_inputs_dict.items():
    if 'timestamp' in child_dict:
        child_dict['timestamp'] = child_dict['timestamp'].isoformat()

for n in sorted_keys:
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

    try:
        dai_id = inputs_dict['dai_id']
        ir_id = inputs_dict['ir_id']
    except:
        calendar_list = service.calendarList().list(pageToken=None).execute()
        for cal in calendar_list['items']:
            if cal['summary'] == f'DAISY{n}':
                dai_id = cal['id']
            elif cal['summary'] == f'DAISY{n} (possibly irrelevant)':
                ir_id = cal['id']

    # Get events, add them to calendar
    checked_urls = []

        # get events, add to calendars
    for term in search_terms:
        events = get_events(term, location,tz)
        #print(events)
        for event in events:
            try:
                if check_if_exists(service, event, dai_id,tz) or check_if_exists(service, event, ir_id,tz):
                    print('checked if exists, it does')
                else:
                    print('checked if exists, it does not')
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
                        if not check_if_exists(service, event, useid, tz):
                            service.events().insert(calendarId=useid, body=event).execute()#service.events().insert(calendarId=useid, body=event).execute()
                    except: # something went wrong adding to calendar
                        print("something went wrong adding "+event['summary']+" to calendar")
                        print(traceback.format_exc())
                        print(' ')
                        print(event)
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
        try:
            notes_real_dict['description'] = str("\n\n".join(not_added))
            service.events().insert(calendarId=dai_id, body=notes_real_dict).execute()
        except:
            pass
    notes_ir_dict = base_event_dict
    if len(unimportant_not_added)>0:
        try:
            notes_ir_dict['description'] = str("\n\n".join(unimportant_not_added))
            service.events().insert(calendarId=ir_id, body=notes_ir_dict).execute()
        except Exception as exe161:
            print(exe161)
    try:
        pass#flag_best(service,tz,dai_id,search_terms,avoid_terms)
    except:
        pass

    time.sleep(5 * 60)
