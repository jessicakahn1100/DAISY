import json
import os
import pickle

#from flask import Flask, render_template, request

#app = Flask(__name__)

#@app.route('/')

here = os.getcwd()
print(here)
client_secret_path = here+r'\client_secret.json'

def run_program():
    #eal_by_title = []
    #eal_by_description = []
    #ot_added = []
    #nimportant_not_added = []
    #kips = []
    printsies = []
    #rintfordebug = []
    search_terms = str(request.form['search_terms']).split(',')
    if len(str(request.form['avoid_terms'])) >= 2:
        avoid_terms = str(request.form['avoid_terms']).split(',')
    else:
        avoid_terms = []
    tz = request.form['timezone']
    city = request.form['city']
    state = request.form['state']
    country = request.form['country']
    try:
        if len(request.form['email'].strip()) < 1:
            print("did not collect email")
        else:
            email = request.form['email']
    except:
        print("did not collect email")
    location = [country,state,city]
    print('beginning for real')
    try:
        print('got here 1.0')
        try:
            print('got here 2.0')
            with open('inpsdict.json', "r") as json_file:
                full_inputs_dict = json.load(json_file)
                ns = []
                for v in full_inputs_dict.keys():
                    ns.append(int(v))
                n = max(ns) + 1
                #print("your user number is "+str(n)+". tell this to Jessica later if you want to edit your inputs.")
                printsies.append("Your user number is "+str(n)+". \nTell this to Jessica later if you want to edit your inputs.")
                #search_terms = request.form['search_terms'].split(',')
                #tz = request.form['timezone']
                #city = request.form['city']
                #state = request.form['state']
                #country = request.form['country']
                full_inputs_dict[n] = {
                    'search_terms':search_terms,
                    'tz':tz,
                    'location':location,
                    'avoid_terms':avoid_terms,
                    'new':'yes'
                }
            with open('inpsdict.json', "w") as json_file:
                json.dump(full_inputs_dict, json_file)
            # {"1": {"search_terms": ["painting", "skating"], "tz": "America/New_York", "location": ["us", "in", "indianapolis"]}}
        except:
            print('got here 3')
            #search_terms = request.form['search_terms'].split(',')
            #tz = request.form['timezone']
            #city = request.form['city']
            #state = request.form['state']
            #country = request.form['country']
            #location = [country,state,city]
            inputs_dict = {
                1:{
                    'search_terms':search_terms,
                    'tz':tz,
                    'location':location
                }
            }
            n = 1
            with open('inpsdict.json', "w") as json_file:
                json.dump(inputs_dict, json_file)
            print('got here 4')
        # evil little monster behavior >:)
            # hehehehe
        #root.destroy()
        try:
            print('got here 5.0')
            with open('service_definition.pkl', 'rb') as f:
                service = pickle.load(f)
        except Exception as a:
            print('got here 6.0')
            print(a)
    except:
        print('got here 8')
        return 8
        #return jsonify({'error': 'File not found >:('})

    # delete DAISY calendar if it exists (used to delete, now just clears)
    calendar_list = service.calendarList().list(pageToken=None).execute()
    for cal in calendar_list['items']:
        if cal['summary'] == f'DAISY{n}':
            service.calendars().delete(calendarId=cal['id']).execute()
    # COLOR ID GUIDE
        # 1 = cocoa
        # 2 = flamingo
        # 3 = tomato
        # 4 = tangerine
        # 5 = pumpkin
        # 6 = mango
        # 7 = eucalyptus
        # 8 = basil
        # 9 = pistacio
        # 10 = avocado
        # 11 = citron
        # 12 = banana
        # 13 = sage
        # 14 = peacock
        # 15 = cobalt
        # 16 = blueberry
        # 17 = lavender
        # 18 = wisteria
        # 19 = graphite
    # make new DAISY calendar
    calendar = {
        'summary': f'DAISY{n}',
        'timeZone': tz
    }
    DAISYcal = service.calendars().insert(body=calendar).execute()
    dai_id = DAISYcal['id']
    try:
        calendar_list_entry = service.calendarList().get(calendarId=dai_id).execute()
        calendar_list_entry['colorId'] = '17'
        DAISYcal = service.calendarList().update(
            calendarId=calendar_list_entry['id'], body=calendar_list_entry).execute()
    except Exception as a:
        print("problem with setting calendar color")
        print(a)
    #debug print('dai id '+dai_id)
    # delete DAISY irrelevant calendar if it exists
    calendar_list = service.calendarList().list(pageToken=None).execute()
    for cal in calendar_list['items']:
        if cal['summary'] == f'DAISY{n} (possibly irrelevant)':
            service.calendars().clear(calendarId=cal['id']).execute()
    # make new DAISY irrelevant calendar
    calendar = {
        'summary': f'DAISY{n} (possibly irrelevant)',
        'timeZone': tz
    }
    DAISYircal = service.calendars().insert(body=calendar).execute()
    ir_id = DAISYircal['id']
    try:
        calendar_list_entry = service.calendarList().get(calendarId=ir_id).execute()
        calendar_list_entry['colorId'] = '19'
        DAISYircal = service.calendarList().update(
            calendarId=calendar_list_entry['id'], body=calendar_list_entry).execute()
    except Exception as a:
        print("problem with setting ir calendar color")
        print(a)
    #debug print('ir id '+ir_id)
    # Get events, add them to calendar
    try:
        rule = {
            'scope': {
                'type': 'user',
                'value': email,
            },
            'role': 'owner'
        }
        service.acl().insert(calendarId=dai_id, body=rule).execute()
        service.acl().insert(calendarId=ir_id, body=rule).execute()
        rulet= "Successfully granted write access to "+email
    except:
        rule = {
            'scope': {
                'type': 'default',
            },
            'role': 'reader',
        }
        service.acl().insert(calendarId=dai_id, body=rule).execute()
        service.acl().insert(calendarId=ir_id, body=rule).execute()
        rulet= "You do not have write access. Ask Jessica about getting write access. Or don't. It's really up to you."

    try:
        with open("newcal.txt",'w') as file:
            file.write(str(n))
    except:
        print("couldn't print to .txt")

    return render_template('output.html',mainlink=f'https://calendar.google.com/calendar/r?cid={dai_id}',irrlink=f'https://calendar.google.com/calendar/r?cid={ir_id}')
    #return {'a':"Subscribe to this calendar.",'b':"It contains events matching your keywords.",'c':"It will update automatically each day. ",'d':f'https://calendar.google.com/calendar/r?cid={dai_id}','e':"Subscribe to this calendar.",'f':"It contains events which appeared in your searches but didn't contain your keywords.",'g':"It will update automatically each day.",'h':f'https://calendar.google.com/calendar/r?cid={ir_id}','i':'THESE CALENDARS ARE NOT GOING TO BE POPULATED WITH EVENTS YET!','j':'The more keywords you have, the longer this will take.','k':"Give it about 10 minutes until you start to see events on the main calendar.",'l':"If more than 10 minutes pass without events populating, tell Jessica.",'m':rulet}

# app.py
from flask import Flask, render_template, request

app = Flask(__name__)

@app.route('/')
def index():
    try:
        return render_template('index.html', states=get_states(), countries=get_countries(), timezones=get_timezones())
    except:
        return {'error': 'template file not found >:('}

@app.route('/run_program', methods=['POST'])
def runprogram():
    print('beginning')
    try:
        b = run_program()
        print('ending')
        return b
    except Exception as b:
        print('grouch')
        return 'grouchy '+str(b)

def get_states():
    return ['al', 'ak', 'az', 'ar', 'ca', 'co', 'ct', 'de', 'dc', 'fl', 'ga', 'hi', 'id', 'il',
            'in', 'ia', 'ks', 'ky', 'la', 'me', 'md', 'ma', 'mi', 'mn', 'ms', 'mo', 'mt', 'ne',
            'nv', 'nh', 'nm', 'ny', 'nc', 'nd', 'oh', 'ok', 'or', 'pa', 'ri', 'sc', 'sd', 'tn',
            'tx', 'ut', 'vt', 'va', 'wa', 'wv', 'wi', 'wy']

def get_countries():
    return ['us', "I didn't add any other countries (yet??)"]

def get_timezones():
    return ['America/New_York', 'America/Chicago', 'America/Los_Angeles']
