import json
import re
import pytz
from datetime import datetime, timedelta, date, timezone
from datetime import time as tii
from dateutil import parser
import requests
from bs4 import BeautifulSoup
import traceback
# for adding to calendar
import os
# for hunting synonyms when GPTs are being uncooperative
from nltk.corpus import wordnet
from urllib.parse import urljoin, urlparse
from collections import Counter

# define some things
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    #'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15',
    #'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
    #'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:88.0) Gecko/20100101 Firefox/88.0',
]
container_keywords = ['view-content','events','container','containter','list','main','calendar','item','section']
date_patterns = [
    [re.compile(r'every (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)', re.IGNORECASE),'weekday'],
    [re.compile(r'\b(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b', re.IGNORECASE),'day','month'],
    [re.compile(r'\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) (\d{1,2})\b', re.IGNORECASE),'month','day'],
    [re.compile(r'\b(\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December)\b', re.IGNORECASE),'day','month'],
    [re.compile(r'\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})\b', re.IGNORECASE),'month','day']
    #,re.compile(, re.IGNORECASE),
    ]
months = {
    'jan':1,
    'feb':2,
    'mar':3,
    'apr':4,
    'may':5,
    'jun':6,
    'jul':7,
    'aug':8,
    'sep':9,
    'oct':10,
    'nov':11,
    'dec':12,
    'january':1,
    'february':2,
    'march':3,
    'april':4,
    'may':5,
    'june':6,
    'july':7,
    'august':8,
    'september':9,
    'october':10,
    'november':11,
    'december':12
}
weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
eventer_dict = {
    'description':['description','details','excerpt'],
    'location':['location','address','venue']
}
tzinfo = {
    "EST": pytz.timezone("America/New_York"),
    "EDT": pytz.timezone("America/New_York"),
    "CST": pytz.timezone("America/Chicago"),
    "CDT": pytz.timezone("America/Chicago"),
    "MST": pytz.timezone("America/Denver"),
    "MDT": pytz.timezone("America/Denver"),
    "PST": pytz.timezone("America/Los_Angeles"),
    "PDT": pytz.timezone("America/Los_Angeles")
}
tzerdict = {
    "America/New_York":'-04:00',
    "America/Chicago":'-05:00',
    "America/Denver":'-06:00',
    "America/Los_Angeles":'-07:00'
    }
# Business rule: keep events of 2 days or less, discard longer ones.
MAX_EVENT_DURATION_DAYS = 2


here = os.getcwd()
print(here)
client_secret_path = here+r'\client_secret.json'

def filter_dicts(d, required_keys):
    """
    Filters dictionaries within a dictionary, keeping only those that contain all required keys.

    :param d: Dictionary containing other dictionaries.
    :param required_keys: Set of keys that each inner dictionary must contain.
    :return: Filtered dictionary.
    """
    filtered_dict = {k: v for k, v in d.items() if required_keys <= v.keys()}
    for e in filtered_dict:
        filtered_dict[e]['colorId'] = '2'
        filtered_dict[e].pop('url', None)
    return filtered_dict

def _parse_event_boundary(event, boundary_key):
    boundary = event.get(boundary_key, {})
    raw_value = boundary.get('dateTime') or boundary.get('date')
    if not raw_value:
        return None
    parsed = parser.isoparse(raw_value)
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed

def is_event_duration_allowed(event, max_days=MAX_EVENT_DURATION_DAYS):
    """
    Return True when event duration is positive and at most max_days.
    Events with missing/invalid dates are treated as invalid and filtered out.
    """
    try:
        start = _parse_event_boundary(event, 'start')
        end = _parse_event_boundary(event, 'end')
        if not start or not end:
            return False
        duration = end - start
        if duration.total_seconds() <= 0:
            return False
        return duration <= timedelta(days=max_days)
    except Exception as parse_error:
        print(f"invalid event duration data for {event.get('summary', 'unknown')}: {parse_error}")
        return False

def ensure_minutes(time_str):
    # Add minutes if they are missing
    if ':' not in time_str:
        time_str = time_str.replace('am', ':00 am').replace('pm', ':00 pm')
        if time_str.endswith('am') or time_str.endswith('pm'):
            return time_str
        return time_str + ':00'
    return time_str

def ensure_am_pm(start_time, end_time):
    # Ensure both times have am/pm indicators
    start_hour = int(start_time.split(':')[0])
    end_hour = int(end_time.split(':')[0])
    if 'am' in end_time.lower() or 'pm' in end_time.lower():
        end_am_pm = 'am' if 'am' in end_time.lower() else 'pm'
    else:
        end_am_pm = None

    if 'am' in start_time.lower() or 'pm' in start_time.lower():
        start_am_pm = 'am' if 'am' in start_time.lower() else 'pm'
    else:
        start_am_pm = None

    if not start_am_pm and end_am_pm:
        if start_hour < end_hour:
            start_am_pm = end_am_pm
        else:
            start_am_pm = 'pm' if end_am_pm == 'am' else 'am'
        start_time = start_time + ' ' + start_am_pm

    if not end_am_pm and start_am_pm:
        if end_hour > start_hour:
            end_am_pm = start_am_pm
        else:
            end_am_pm = 'pm' if start_am_pm == 'am' else 'am'
        end_time = end_time + ' ' + end_am_pm

    if not start_am_pm and not end_am_pm:
        start_time += ' am'
        end_time += ' pm'

    return start_time, end_time

def parse_time_range(match):

    start_time_str = match[0]
    end_time_str = match[1]

    try:
        start_time = datetime.strptime(start_time_str, '%I:%M %p').time()
    except:
        # Ensure minutes are present
        start_time_str = ensure_minutes(start_time_str)
        end_time_str = ensure_minutes(end_time_str)
        # Ensure am/pm indicators are present
        start_time_str, end_time_str = ensure_am_pm(start_time_str, end_time_str)
        # Convert to datetime.time objects
        start_time = datetime.strptime(start_time_str, '%I:%M %p').time()
        #end_time = datetime.strptime(end_time_str, '%I:%M %p').time()
    try:
        end_time = datetime.strptime(end_time_str, '%I:%M %p').time()
    except:
        # Ensure minutes are present
        start_time_str = ensure_minutes(start_time_str)
        end_time_str = ensure_minutes(end_time_str)
        # Ensure am/pm indicators are present
        start_time_str, end_time_str = ensure_am_pm(start_time_str, end_time_str)
        # Convert to datetime.time objects
        #start_time = datetime.strptime(start_time_str, '%I:%M %p').time()
        end_time = datetime.strptime(end_time_str, '%I:%M %p').time()

    return start_time, end_time

def single_event_pager(soup,tz):
    singleevent = {}
    singleevent['description'] = '\n'.join((ccse.get_text()+' ') for ccse in soup.find(re.compile('^h[1-6]$')).find_all_next('p')).replace(r'\n','\n').replace('\\n','\n').replace('Time: ',' ')
    try:
        souptext = ''
        for textie in soup.find_all(string=True):
            try:
                souptext += (textie.get_text()+' ')
            except:
                pass
        for date_pattern in date_patterns:
            try:
                singleevent['datehold'] = date_pattern[0].findall(souptext)[0]
                singleevent['datepattern'] = date_pattern[1:]
                break
            except:
                pass
        try:
            timeholdcandidates = re.findall(r'\b(\d{1,2}(?::\d{2})? ?[APap][Mm]) ?[-–] ?(\d{1,2}(?::\d{2})? ?[APap][Mm])\b',souptext)
            for thc in timeholdcandidates:
                thc = list(thc)
                try:
                    singleevent['timehold'] = parse_time_range(thc)
                    break
                except:
                    pass
                    #print(traceback.format_exc())
            if not 'timehold' in singleevent:
                singleevent['timehold'] = parse_time_range("12:00 am to 12:05 am")
        except:
            pass
        # if can't do anything, don't
        if not 'datehold' in singleevent or not 'timehold' in singleevent:
            raise Exception
        # deal with date
        if len(singleevent['datepattern']) == 1: # if this is a weekly event
            singleevent['datehold'] = (datetime.today() + timedelta(days=(weekdays.index(singleevent['datehold'].lower()) - datetime.today().weekday() + 7) % 7)).date()
            singleevent['recurrence']=['RRULE:FREQ=WEEKLY;COUNT=5']
        else:
            if singleevent['datepattern'][0] == 'month':
                singleevent['datehold'] = [months[singleevent['datehold'][0].lower()],int(singleevent['datehold'][1])]
            else:
                singleevent['datehold'] = [months[singleevent['datehold'][1].lower()],int(singleevent['datehold'][0])]
            if date.today() > date(datetime.today().year,singleevent['datehold'][0],int(singleevent['datehold'][1])):
                singleevent['datehold'] = date(datetime.today().year+1,singleevent['datehold'][0],singleevent['datehold'][1])
            else:
                singleevent['datehold'] = date(datetime.today().year,singleevent['datehold'][0],singleevent['datehold'][1])
        # make datetime
        singleevent['start'] = {
            'dateTime': datetime.combine(singleevent['datehold'],singleevent['timehold'][0]).isoformat(),
            'timeZone': tz
        }
        singleevent['end'] = {
            'dateTime': datetime.combine(singleevent['datehold'],singleevent['timehold'][1]).isoformat(),
            'timeZone': tz
        }
        singleevent['reminders'] = {
            'useDefault': False,
            'overrides': [
            ],
        }
        del singleevent['timehold']
        del singleevent['datehold']
        del singleevent['datepattern']
    except:
        singleevent['reminders'] = {
            'useDefault': False,
            'overrides': [
            ],
        }
        singleevent['start'] = {'timeZone':tz}
        singleevent['end'] = {'timeZone':tz}
        for thingy in [singleevent['description'].split('am')[0],singleevent['description'].split('pm')[0],singleevent['description'],souptext.split('am')[0],souptext.split('pm')[0]]:
            try:
                timehold = parser.parse(thingy, fuzzy=True)
                break
            except:
                pass#print(traceback.format_exc())
        singleevent['start']['dateTime'] = timehold.isoformat()
        singleevent['end']['dateTime'] = (timehold+timedelta(minutes=5)).isoformat()
        for k in ['timehold','datehold','datepattern']:
            try:
                del singleevent[k]
            except:
                pass
    return singleevent

def event_puller(elements,n,baseurl,tz):
    targes = []
    events = {}
    for element in elements:
        try:
            try:
                href = element['href']
            except:
                href = element.find(href=True)['href']
            if 'https' not in href:
                href = urljoin(baseurl, href)
            d = [href,element.find(re.compile('^h[1-6]$')).get_text().strip()]
            targes.append(tuple(d))
        except:
            pass
    for element in [list(tpl) for tpl in list(set(targes))]:
        n+=1
        events[f'general {n}'] = {
            'url':element[0],
            'summary':element[1]
        }
        childchildsoup = BeautifulSoup(requests.get(element[0]).text,'html.parser')
        try:
            events[f'general {n}'] = events[f'general {n}'] | single_event_pager(childchildsoup,tz)
        except:
            pass
    return events,n

def get_events_from_site_with_list(url,n,tz):
    parsed_url = urlparse(url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    events = {}
    for user_agent in user_agents:
        try:
            soup = BeautifulSoup(requests.get(url,headers={"User-Agent":user_agent}).text,'html.parser')
            break
        except:
            pass #print(traceback.format_exc())
    try:
        potential_containers = set()
        for element in soup.find_all(class_=True):
            potential_containers.add(element)
            potential_containers.update(element.find_all(class_=True))
        # Create a list of tuples with container and length of its children vector
        containers_with_lengths = [
            (container, len(container.find_all('div', recursive=False, class_=True)))
            for container in potential_containers
        ]
        # Sort the list by length of children vectors in descending order
        sorted_containers = [container for container, length in sorted(containers_with_lengths, key=lambda x: x[1], reverse=True)]
        # Iterate over the sorted containers
        for container in sorted_containers:
            class_names = ' '.join(container.get('class', [])).lower()
            if any(keyword in class_names for keyword in container_keywords):
                children = container.find_all('div', recursive=False, class_=True)
                if children:
                    # Find the most frequent class among the children
                    class_counts = Counter([' '.join(child.get('class', [])) for child in children])
                    most_frequent_class = class_counts.most_common(1)[0][0]
                    # Filter children to include only those with the most frequent class
                    children = [child for child in children if ' '.join(child.get('class', [])) == most_frequent_class]
                    # Proceed with processing these filtered children
                    if children:
                        #print(f'victory: {most_frequent_class}')
                        events, n = event_puller(children, n, base_url, tz)
                        events = filter_dicts(events, {'start', 'end', 'summary', 'description'})
                        if events:
                            print(f'len events = {len(events)}')
                            return events, n
                        else: # if event puller didn't work for some reason
                            try:
                                ##print('doing on this page')
                                events = {}
                                for child in children:
                                    events[f'general {n}'] = {}
                                    events[f'general {n}']['start'] = {}
                                    events[f'general {n}']['end'] = {}
                                    try:
                                        events[f'general {n}']['summary'] = child.find(re.compile('^h[1-6]$')).get_text().strip()
                                        for infocat in eventer_dict.keys():
                                            for keyword in eventer_dict[infocat]:
                                                try:
                                                    events[f'general {n}'][infocat] = child.find(class_=re.compile(f'.*{keyword}.*')).get_text().strip().replace('\t','').replace('\n','').replace('•','')
                                                    break
                                                except:
                                                    pass
                                        events[f'general {n}']['start']['timeZone'] = tz
                                        events[f'general {n}']['end']['timeZone'] = tz
                                        for keyword in ['start','datetime','date','time']:
                                            try:
                                                timehold = parser.parse(child.find(class_=re.compile(f'.*{keyword}.*')).get_text().strip(), fuzzy=True)
                                                events[f'general {n}']['start']['dateTime'] = timehold.isoformat()
                                                events[f'general {n}']['end']['dateTime'] = (timehold+timedelta(minutes=5)).isoformat()
                                                break
                                            except:
                                                timehold = parser.parse(child.get_text().strip(), fuzzy=True)
                                                events[f'general {n}']['start']['dateTime'] = timehold.isoformat()
                                                events[f'general {n}']['end']['dateTime'] = (timehold+timedelta(minutes=5)).isoformat()
                                        try:
                                            events[f'general {n}']['description'] = events[f'general {n}']['description'] + ' \n ' + url
                                        except:
                                            events[f'general {n}']['description'] = url
                                        n += 1
                                    except:
                                        pass
                                        #print(traceback.format_exc())
                                events = filter_dicts(events, {'start', 'end', 'summary', 'description'})
                                if len(events.keys()) > 0:
                                    return events, n
                                else:
                                    pass
                            except:
                                #print(traceback.format_exc())
                                pass
    except:
        #print(traceback.format_exc())
        return {},n

def scrape_anybody(kwd,location,tz):
    events_all = {}
    n = 0
    googleurl = f'https://www.google.com/search?q={kwd.replace(" ","+")}+events+{location[2].replace(" ","+")}#ip=1'
    print(googleurl)
    response = requests.get(googleurl)
    soup = BeautifulSoup(response.text, 'html.parser')
    childurlelms = soup.find_all(lambda tag: tag.has_attr('href') and tag.has_attr('data-ved'))
    childurls = []
    for childurlelm in childurlelms:
        try:
            href = 'https://'+"/".join(childurlelm['href'].split('https://')[1].split('/')[:-1])
            if 'event' in href and not any((source in href) for source in ['eventbrite','meetup','allevents.in']):
                childurls.append(href)
        except:
            pass
    print(list(set(childurls)))
    for childurl in list(set(childurls)):
        print(childurl)
        try:
            responsee = requests.get(childurl).status_code
            if responsee != 200:
                continue
        except:
            continue
        try:
            [events,n] = get_events_from_site_with_list(childurl,n,tz)
            events_all = events_all | events
            if len(events.keys()) < 1:
                raise Exception
        except:
            ##print('doing single')
            try:
                n += 1
                childsoup = BeautifulSoup(requests.get(childurl).text,'html.parser')
                events_all[f'general {n}'] = {
                    'url':childurl,
                    'summary':childsoup.find(re.compile('^h[2-6]$')).get_text().strip()
                    }
                events_all[f'general {n}'] = events_all[f'general {n}'] | single_event_pager(childsoup,tz)
                n += 1
            except:
                #print(traceback.format_exc())
                pass

    events_all = filter_dicts(events_all, {'start','end','summary','description'})
    return events_all

def scrape_meetup(search_term,location,tz):
    search_term = search_term.replace(" ","%20")
    location[2] = location[2].replace(" ","%20")
    events = {}
    n = 0
    for w in ['this-week','this-weekend','next-week']:
        meetup_url = f"https://www.meetup.com/find/?allMeetups=true&location={location[0]}--{location[1]}--{location[2]}&keywords={search_term}&source=EVENTS&eventType=inPerson&dateRange={w}"
        print(meetup_url)
        response = requests.get(meetup_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        edicts_ = json.loads(soup.find(attrs={'type':'application/json'}).decode_contents())['props']['pageProps']['__APOLLO_STATE__']
        edicts = []
        venuedicts = {}
        #input(edicts_)
        for b in edicts_:
            if isinstance(edicts_[b],dict) and 'Event' in b:
                if 'title' in edicts_[b]:
                    edicts.append(edicts_[b])
                    #input(edicts_[b])
                    #print('')
            elif isinstance(edicts_[b],dict) and 'Venue' in b:
                venuedicts = venuedicts | edicts_[b]
        for edict in edicts:
            try:
                events["meetup"+str(n)] = {}
                events["meetup"+str(n)]['summary'] = edict['title']
                events["meetup"+str(n)]['description'] = edict['description']+'\n\n'+edict['eventUrl']
                events["meetup"+str(n)]['start'] = {'dateTime':edict['dateTime'],'timeZone':tz}#{'dateTime':edict['dateTime'][:-6]+'z','timeZone':tz}
                events["meetup"+str(n)]['end'] = {'dateTime':edict['dateTime'][:-10]+'5:00'+edict['dateTime'][-6:],'timeZone':tz}#{'dateTime':edict['dateTime'][:-10]+'5:00z','timeZone':tz}
                events["meetup"+str(n)]['colorId'] = '10'
                try:
                    events["meetup"+str(n)]['location'] = venuedicts[edict['venue']['__ref']]['name']
                except:
                    pass
                try:
                    eresponse = requests.get(edict['eventUrl'])
                    esoup = BeautifulSoup(eresponse.text, 'html.parser')
                    eedict = json.loads(esoup.find_all(attrs={'type':'application/ld+json'})[1].decode_contents())
                    events["meetup"+str(n)]['end'] = {'dateTime':eedict['endDate'],'timeZone':tz}#{'dateTime':eedict['endDate'][:-6]+'z','timeZone':tz}
                except:
                    pass
                n += 1
            except Exception as exce:
                print('failure')
                print(events["meetup"+str(n)])
                print(' '*5)
                print(traceback.format_exc())
                print(' '*5)
                print(edict)
                print(' '*5)
    return events

def scrape_eventbrite(search_term, location, tz):
    search_term = search_term.replace(" ","-")
    location[2] = location[2].replace(" ","-")
    events = {}
    n = 0
    for when in ["this-week","next-week"]:
        for pageno in [1,2]:
            url = f"https://www.eventbrite.com/d/{location[1]}--{location[0]}/events--{when}/{search_term}/?page={pageno}"
            response = requests.get(url,headers = {'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'})#.pagesource
            soup = BeautifulSoup(response.text, 'html.parser')
            edicts = soup.find_all(attrs={'type':'application/ld+json'})
            for edict in edicts[:-1]:
                try:
                    edict = json.loads(edict.decode_contents())['itemListElement'][0]['item']
                    events['eventbrite'+str(n)] = {}
                    events['eventbrite'+str(n)]['summary'] = edict['name'].replace(r'&amp;',r'&')
                    try:
                        try:
                            events["eventbrite"+str(n)]['location'] = edict['location']['name']
                        except:
                            events["eventbrite"+str(n)]['location'] = edict['location']['address']['streetAddress']
                    except:
                        try:
                            events["eventbrite"+str(n)]['location'] = edict['location']['geo']
                        except:
                            pass#events["eventbrite"+str(n)]['location'] = "check the URL"
                    eeurl = edict['url']
                    events['eventbrite'+str(n)]['description'] = edict['description'].replace(r'&amp;',r'&') + ' \n ' + edict['url']
                    events['eventbrite'+str(n)]['start'] = {'dateTime':parser.parse(edict['startDate']).isoformat,'timeZone':tz}
                    events['eventbrite'+str(n)]['end'] = {'dateTime':parser.parse(edict['endDate']).isoformat,'timeZone':tz}
                    try:
                        esoup = BeautifulSoup(requests.get(eeurl,headers = {'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'}).text, 'html.parser')
                        events['eventbrite'+str(n)]['start'] = {'dateTime':esoup.find(attrs={'property':'event:start_time'}).get('content'),'timeZone':tz}
                        events['eventbrite'+str(n)]['end'] = {'dateTime':esoup.find(attrs={'property':'event:end_time'}).get('content'),'timeZone':tz}
                        events['eventbrite'+str(n)]['colorId'] = '9'
                    except:
                        print(f'eventbrite experienced failure at 2 for n = {n}')
                        print(traceback.format_exc())
                    print(f'eventbrite experienced success at 1 for n = {n}')
                    n += 1
                except Exception:
                    print(f'eventbrite experienced failure at 1 for n = {n}')
                    print(edict)
                    print(traceback.format_exc())
    return events

def scrape_google(search_term,location,tz):
    search_term = search_term.replace(" ","+")
    location[2] = location[2].replace(" ","+")
    url = f'https://www.google.com/search?q={location[2]}+{search_term}+events&ibp=htl;events#htivrt=events'
    print(url)
    response = requests.get(url,headers = {'User-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'})#.pagesource
    soup = BeautifulSoup(response.text, 'html.parser')
    events = {}
    n = 0

    for e in soup.find_all(attrs={'class':'gws-horizon-textlists__li-ed'}):
        try:
            #print(f'e {e}')
            events['google'+str(n)] = {}
            events['google'+str(n)]['summary'] = e.find(attrs={'class':'YOGjf'}).decode_contents().replace(r'&amp;',r'&')#[n]
            events['google'+str(n)]['colorId'] = '7'
            events['google'+str(n)]['location'] = e.find_all(attrs={'class':'cEZxRc'})[1].decode_contents()#[n*2]
            events['google'+str(n)]['description'] = e.find(attrs={'class':'PVlUWc'}).decode_contents().replace(r'&amp;',r'&') + ' \n ' + e.find(attrs={'class':'zTH3xc'}).get('href')
            #events['google'+str(n)]['url'] = e.find(attrs={'class':'zTH3xc'}).get('href')
            #try:
            #    events['google'+str(n)]['Picture'] = e.find(attrs={'class':'YQ4gaf'}).get('src')
            #except:
            #    pass
            tstring = e.find(attrs={'class':'Gkoz3'}).decode_contents()
            #print(f'tstring {tstring}')
            tzc = None
            for tzi in tzinfo.keys():
                if tzi in tstring:
                    tzc = tzi
                    tzcode = tzinfo[tzi]
            tdict = {'month0': None, 'time0': None, 'AMPM0': None, 'day0': None, 'year0': None,
                       'month1': None, 'time1': None, 'AMPM1': None, 'day1': None, 'year1': None}
            for nn in [0, 1]:
                # splitting into start and end
                try:
                    ststring = tstring.split('–')[nn].strip()
                except:
                    ststring = tstring.split(' – ')[nn].strip()
                # Extracting month
                holdmon = 'zzzzzzzzzzz' # placeholder which will never appear in time strings
                if any(month in ststring for month in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']):
                    for mon in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                        if mon in ststring:
                            holdmon = mon
                            tdict[f'month{nn}'] = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(mon)+1
                # Extracting day
                day_match = re.search(str(tdict[f'month{nn}'])+r' (\b\d{1,2}\b)', ststring)
                #if day_match:
                #    day_match = day_match.group()
                #    if day_match[:len(tdict[f'month{nn}'])] == tdict[f'month{nn}']:
                #        day_match = day_match[3:]
                #    if day_match[1] == ',':
                #        day_match = day_match[0]
                #    tdict[f'day{nn}'] = int(day_match)
                try:
                    tdict[f'day{nn}'] = int(ststring.split(holdmon)[1].split(',')[0].strip())
                except:
                    pass
                # Extracting year
                year_match = re.search(r'(\b\d{4}\b)', ststring)
                if year_match:
                    tdict[f'year{nn}'] = int(year_match.group())
                else:
                    tdict[f'year{nn}'] = None
                # Extracting AM/PM
                if 'AM' in ststring:
                    tdict[f'AMPM{nn}'] = 'AM'
                elif 'PM' in ststring:
                    tdict[f'AMPM{nn}'] = 'PM'
                # Extracting time
                if 'AM' in ststring or 'PM' in ststring:
                    try:
                        tdict[f'time{nn}'] = ststring.replace('AM','').replace('PM','').replace(tzc,'').strip().split(' ')[-1]
                    except:
                        tdict[f'time{nn}'] = ststring.replace('AM','').replace('PM','').strip().split(' ')[-1]
                else:
                    time_match = re.search(r'(\d{1,2}:\d{2})\s*([APMapm]{2})?', ststring)
                    if time_match:
                        tdict[f'time{nn}'] = time_match.group(1)
                    else:
                        # Extracting time without minutes or AM/PM flag
                        time_without_minutes_match = ('AM' in ststring or 'PM' in ststring)
                        if time_without_minutes_match and day_match:
                            try:
                                h = int(ststring[-2:].strip())
                                tdict[f'time{nn}'] = tii(hour=h)
                            except:
                                pass
            # meshing
            for [i,noti] in [[0,1],[1,0]]:
                for w in ['month','time','AMPM','day']:
                    if not tdict[f'{w}{i}']:
                        tdict[f'{w}{i}'] = tdict[f'{w}{noti}']
            # time meshing fix
            if not tdict['time0']:
                tdict['time0'] = '12:01'
                tdict['time1'] = '11:59'
                tdict['AMPM0'] = 'AM'
                tdict['AMPM1'] = 'PM'
            if not ':' in tdict['time0']:
                tdict['time0'] += ':00'
            if not ':' in tdict['time1']:
                tdict['time1'] += ':00'
            # month meshing fix
            if not tdict['month0']:
                tdict['month0'] = datetime.now().month
                tdict['month1'] = datetime.now().month
            # year meshing fix
            if tdict['year0'] and tdict['month1'] < tdict['month0']:
                tdict['year1'] = tdict['year0']+1
            elif tdict['year0']:
                tdict['year1'] = tdict['year0']
            elif tdict['year1'] and tdict['month1'] < tdict['month0']:
                tdict['year0'] = tdict['year1']-1
            elif tdict['year1']:
                tdict['year0'] = tdict['year1']
            else:
                tdict['year0'] = datetime.now().year
                tdict['year1'] = datetime.now().year
            # datetiming
            try:
                events['google'+str(n)]['start'] = {'dateTime':datetime.strptime(f"{tdict['year0']} {tdict['month0']} {tdict['day0']} {tdict['time0']} {tdict['AMPM0']}",'%Y %m %d %I:%M %p').isoformat(),'timeZone':tz}
                events['google'+str(n)]['end'] = {'dateTime':datetime.strptime(f"{tdict['year1']} {tdict['month1']} {tdict['day1']} {tdict['time1']} {tdict['AMPM1']}",'%Y %m %d %I:%M %p').isoformat(),'timeZone':tz}
            except Exception as exce:
                print(exce)
                print(tstring)

            n += 1
        except Exception as exception:
            print(f'exception {exception}')

    return events

def get_events(search_term,location,tz):
    # Call the scrape functions for Meetup, Eventbrite, and Google Events
    try:
        eventbrite_events = scrape_eventbrite(search_term,location,tz)
    except Exception as eventbrite:
        eventbrite_events = {}
        print('problem with eventbrite '+str(eventbrite))
    try:
        meetup_events = scrape_meetup(search_term,location,tz)
    except Exception as meetup:
        meetup_events = {}
        print('problem with meetup '+str(meetup))
    try:
        google_events = scrape_google(search_term,location,tz)
    except Exception as google:
        google_events = {}
        print('problem with google '+str(google))
    try:
        any_events = scrape_anybody(search_term,location,tz)
    except Exception as anybody:
        any_events = {}
        print('problem with google '+str(anybody))

    # Combine the events from all sources into a single list
    all_events = meetup_events | eventbrite_events | google_events | any_events

    filtered_events = []
    for event in all_events.values():
        if is_event_duration_allowed(event):
            filtered_events.append(event)
        else:
            print(f"skipped long/invalid event: {event.get('summary', 'unknown')}")
        #print(event)
        #print(' ')
        #print(' ')

    return filtered_events

def _location_key(location):
    return tuple(str(part).strip().lower() for part in location)

def _search_term_key(search_term):
    return str(search_term).strip().lower()

def build_city_event_pool(full_inputs_dict, user_ids):
    city_searches = {}
    for user_id in user_ids:
        inputs_dict = full_inputs_dict[user_id]
        location = inputs_dict['location']
        city_key = _location_key(location)
        if city_key not in city_searches:
            city_searches[city_key] = {
                'location': list(location),
                'tz': inputs_dict['tz'],
                'terms': {}
            }
        for search_term in inputs_dict.get('search_terms', []):
            cleaned_term = str(search_term).strip()
            if not cleaned_term:
                continue
            city_searches[city_key]['terms'].setdefault(_search_term_key(cleaned_term), cleaned_term)

    city_events = {}
    for city_key, city_config in city_searches.items():
        pooled_events = []
        seen_events = set()
        for search_term in city_config['terms'].values():
            events = get_events(search_term, list(city_config['location']), city_config['tz'])
            for event in events:
                event_key = (
                    event.get('summary'),
                    str(event.get('start', {}).get('dateTime')),
                    str(event.get('location'))
                )
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)
                pooled_events.append(event)
        city_events[city_key] = pooled_events

    return city_events

def get_city_events_for_user(city_events, location):
    return city_events.get(_location_key(location), [])

def check_if_exists(service, event, id, tz): # true if already exists on calendar, false otherwise
    try:
        timemin = event['start']['dateTime'].replace('z', '')
        timemax = (datetime.fromisoformat(event['start']['dateTime'].replace('z', '')) + timedelta(minutes = 5)).isoformat()
        if timemin[-len(tzerdict[tz]):] != tzerdict[tz]:
            timemin = timemin+tzerdict[tz]
            timemax = timemax+tzerdict[tz]
        try:
            # look for deleted events
            existing_events = service.events().list(calendarId=id,timeMin=timemin,timeMax=timemax,timeZone=tz,showDeleted=True,q=event['summary']).execute()
            for existing_event in existing_events['items']:
                if event['summary'] == existing_event['summary']:
                    return True
            return False
        except Exception as aa:
            print(aa)
            existing_events = service.events().list(calendarId=id,timeMin=timemin,timeMax=timemax,timeZone=tz).execute()
            for existing_event in existing_events['items']:
                if event['summary'] == existing_event['summary']:
                    return True
            return False
    except Exception as a:
        print(' '*50)
        print("something evil happened while trying to find duplicate events for "+str(event['summary']))
        print(a)
        print(traceback.format_exc())
        print(event['start'])
        print(event['start'])
        print(' '*50)
        return False
    return False

def get_synonyms(word):
    synonyms = []
    for syn in wordnet.synsets(word):
        for lemma in syn.lemmas():
            synonyms.append(lemma.name())
    L = list(set(synonyms))
    if word[-1] == 's':
        L.append(word[:-1])
    elif word[-3] == 'ing':
        L.append(word[:-3])
    elif word == 'cycling':
        L += ['biking','ride','bike','cycle']
    elif word == 'makerspace':
        L += ['art studio','art lesson','art class','craft studio','craft lesson','craft class']
    return L

def check_relevance(event,search_terms,avoid_terms,block_terms):
    # check for search term
    hasterm = False
    for term in search_terms:
        try:
            if any(sterm.upper() in str(event['summary']).upper() or sterm.upper() in str(event['description']).upper() for sterm in get_synonyms(term)):
               hasterm = True
        except:
            if term.upper() in str(event['summary']).upper() or term.upper() in str(event['description']).upper:
                hasterm = True
        if hasterm:
            break
    # check for avoid terms
    avoid = False
    if avoid_terms:
        # adjust avoid terms
        add_avoids = []
        if "for kids" in avoid_terms:
            add_avoids += ["for children","for ages","kid-focused","parents","childrens","children's",'kids',"kid's"]
        if "for couples" in avoid_terms:
            add_avoids += ["date night","couple date","romantic"]
        if "for christians" in avoid_terms or "religious" in avoid_terms or "for Christians" in avoid_terms:
            add_avoids += ["religious","Jesus","Christ ","preacher","pastor","priest"]
        if "like job fairs" in avoid_terms:
            add_avoids += ["employment","job fair","communication seminar","communication workshop","entrepreneur"]
        if any(aterm.upper() in str(event['summary']).upper() or aterm.upper() in str(event['description']).upper() for aterm in avoid_terms):
            avoid = True
        if any(aaterm.upper() in str(event['summary']).upper() or aaterm.upper() in str(event['description']).upper() for aaterm in add_avoids):
            avoid = True
    # check for block terms
    block = False
    if block_terms:
        if any(bterm.upper() in str(event['summary']).upper() or bterm.upper() in str(event['description']).upper() for bterm in block_terms):
            block = True
    # decide what to do [relevant,show]
    if block:
        return False,False
    elif hasterm and not avoid:
        return True,True
    else:
        return False,True

# COLOR ID GUIDE
    # https://google-calendar-simple-api.readthedocs.io/en/latest/colors.html

def find_favorites(service,tz,dai_id,cal_color):
    seven_days_ago = (datetime.now() - timedelta(days = 7)).replace(hour=0).isoformat()+"z"
    now = datetime.now().isoformat()+"z"
    existing_events = service.events().list(calendarId=dai_id,timeMin=seven_days_ago,timeMax=now,timeZone=tz).execute() # ,showDeleted=False
    #events_by_id = {}
    #events_by_summary = {}
    statement = ""
    #cal_color = service.colors().get(calendarId=dai_id).execute()
    for event in existing_events['items']:
        event_color = service.events().get(calendarId=dai_id, eventId=event['id']).execute().get('colorId')
        if event_color == cal_color: # if this event hasn't been flagged, skip
            print('not '+event['summary'])
            pass
        elif event_color == '5': # if event has been auto-flagged as banana, skip
            print('banana: not '+event['summary'])
            pass
        elif not event_color:
            print('not '+event['summary'])
            pass
        else: # if event has been manually flagged, store info
            #events_by_id[event['id']] = event['summary']
            #events_by_summary[event['summary']] = event['id']
            statement = statement+event['summary']+", "#event_color+"; "
    if len(statement) > 1:
        statement = statement[:-2]
        statement = statement
        return statement
    else:
        return False

def flag_best(service,tz,dai_id,search_terms,avoid_terms):
    cal_color = service.calendars().get(calendarId=dai_id).execute().get('backgroundColor') #service.colors().get(calendarId=dai_id).execute()
    print(cal_color)
    now = datetime.now().isoformat()+"z"
    #print(now)
    three_days_ahead = (datetime.now() + timedelta(days = 3)).replace(hour=0).isoformat()+"z"
    #print(three_days_ahead)
    existing_events1 = service.events().list(calendarId=dai_id,timeMin=now,timeMax=three_days_ahead,timeZone=tz).execute() #,showDeleted=False
    events_by_summary = {}
    event_statement = ""
    for event in existing_events1['items']:
        event_color = service.events().get(calendarId=dai_id, eventId=event['id']).execute().get('colorId')
        if event_color == cal_color and event['summary'] != "NOTES ON EVENTS NOT ADDED TO CALENDAR":
            events_by_summary[event['summary']] = event
            event_statement += event['summary']+"; /n"
        elif not event_color and event['summary'] != "NOTES ON EVENTS NOT ADDED TO CALENDAR":
            events_by_summary[event['summary']] = event
            event_statement += event['summary']+"; /n"
        elif event_color == '5': # if already have a banana event within next three days
            return True
        else:
            pass
    fave_statement = find_favorites(service,tz,dai_id,cal_color)
    seven_days_ahead = (datetime.now() + timedelta(days = 7)).replace(hour=0).isoformat()+"z"
    existing_events2 = service.events().list(calendarId=dai_id,timeMin=three_days_ahead,timeMax=seven_days_ahead,timeZone=tz).execute() #,showDeleted=False
    for event in existing_events2['items']:
        event_color = service.events().get(calendarId=dai_id, eventId=event['id']).execute().get('colorId')
        if event_color == cal_color and event['summary'] != "NOTES ON EVENTS NOT ADDED TO CALENDAR":
            events_by_summary[event['summary']] = event
            event_statement += event['summary']+"; /n"
        else:
            pass
    gptheaders = {
    	"content-type": "application/json",
    	"X-RapidAPI-Key": "d763cd0cd9msh31d76766c432afap107663jsn2dd139de41ef",
    	"X-RapidAPI-Host": "gpts4u.p.rapidapi.com"
    }
    try:
        searchs = ", ".join(search_terms)
    except:
        searchs = search_terms
    if not event_statement:
        return False
    if avoid_terms:
        try:
            avoids = ", ".join(avoid_terms)
        except:
            avoids = avoid_terms
        if fave_statement:
            statement = "My interests include "+searchs+". I do not like events "+avoids+". Last week, my favorite events were "+fave_statement+". This week, events on my agenda include "+event_statement+". Which event on my agenda this week do you think I'll enjoy most? Respond only with the title of the event."
        else:
            statement = "My interests include "+searchs+". I do not like events "+avoids+". This week, events on my agenda include "+event_statement+". Which event on my agenda this week do you think I'll enjoy most? Respond only with the title of the event."
    else:
        if fave_statement:
            statement = "My interests include "+searchs+". Last week, my favorite events were "+fave_statement+". This week, events on my agenda include "+event_statement+". Which event on my agenda this week do you think I'll enjoy most? Respond only with the title of the event."
        else:
            statement = "My interests include "+searchs+". This week, events on my agenda include "+event_statement+". Which event on my agenda this week do you think I'll enjoy most? Respond only with the title of the event."
    print(statement)
    gptpayload = [
    	{
    		"role": "user",
    		"content": statement
    	}
    ]
    querystring = {"role": "user","content": statement}
    try:
        gpturl = "https://gpts4u.p.rapidapi.com/bingChat" # updated to Bing Chat from Llamas2
        gptresponse = requests.post(gpturl, json=gptpayload, headers=gptheaders, params=querystring).json()
        print(gptresponse)
        b = 0
        for summary in events_by_summary.keys():
            if summary.upper() in gptresponse.upper():
                id = events_by_summary[summary]['id']
                event = events_by_summary[summary]
                event['colorId'] = '5' # make event banana
                updated_event = service.events().update(calendarId=dai_id, eventId=id, body=event).execute()
                print('made '+summary+' banana')
                b +=1
                if b >= 2:
                    break
            else:
                pass
            if b == 0:
                gpturl = "https://gpts4u.p.rapidapi.com/llama2" # updated to Bing Chat from Llamas2
                try:
                    gptresponse = requests.post(gpturl, json=gptpayload, headers=gptheaders).json()
                    print(gptresponse)
                except:
                    gptresponse = 'b'
                    print(requests.post(gpturl, json=gptpayload, headers=gptheaders, params=querystring).status_code)
                res = gptresponse.upper()
                print(res.replace(" ",""))
                for summary in events_by_summary.keys():
                    #print(summary)
                    su = summary.upper()
                    print(su.replace(" ",""))
                    if su.replace(" ","") in res.replace(" ",""):
                        print(summary)
                        eid = events_by_summary[summary]['id']
                        event = events_by_summary[summary]
                        #event['colorId'] = '12' # make event banana
                        event = {
                            'summary':event['summary'],
                            'description':event['description'],
                            'location':event['location'],
                            'start':event['start'],
                            'end':event['end'],
                            'reminders':event['reminders'],
                            'colorId':'5' # make event banana
                        }
                        print(event)
                        updated_event = service.events().update(calendarId=dai_id, eventId=eid, body=event).execute()
                        print('made '+summary+' banana')
                        b +=1
                        if b >= 2:
                            break
                    else:
                        pass
    except:
        if not b:
            b = 0
        gpturl = "https://gpts4u.p.rapidapi.com/llama2" # updated to Bing Chat from Llamas2
        try:
            gptresponse = requests.post(gpturl, json=gptpayload, headers=gptheaders).json()
            print(gptresponse)
        except:
            gptresponse = 'b'
            print(requests.post(gpturl, json=gptpayload, headers=gptheaders, params=querystring).status_code)
        res = gptresponse.upper()
        print(res.replace(" ",""))
        for summary in events_by_summary.keys():
            #print(summary)
            su = summary.upper()
            print(su.replace(" ",""))
            if su.replace(" ","") in res.replace(" ",""):
                print(summary)
                eid = events_by_summary[summary]['id']
                event = events_by_summary[summary]
                #event['colorId'] = '12' # make event banana
                event = {
                    'summary':event['summary'],
                    'description':event['description'],
                    'location':event['location'],
                    'start':event['start'],
                    'end':event['end'],
                    'reminders':event['reminders'],
                    'colorId':'5' # make event banana
                }
                print(event)
                service.events().update(calendarId=dai_id, eventId=eid, body=event).execute()
                print('made '+summary+' banana')
                b +=1
                if b >= 2:
                    break
            else:
                pass
    return
