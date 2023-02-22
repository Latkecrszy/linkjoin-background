from pymongo import MongoClient
import os, dotenv, requests, time as t, datetime, json
from argon2 import PasswordHasher

ph = PasswordHasher()
dotenv.load_dotenv()
VONAGE_API_KEY = os.environ.get("VONAGE_API_KEY", None)
VONAGE_API_SECRET = os.environ.get("VONAGE_API_SECRET", None)
mongo = MongoClient(os.environ.get('MONGO_URI', None))

"""
TASKS:
1. Send text reminders
2. Delete OTPs/update remaining time
3. Update repeat/occurrences
4. Delete tokens/update remaining time
5. Report time total process took


TODO OVERALL: Update repeat/occurrences system to make sense



"""


def message():
    # Create an empty dictionary to store changes for group write to database
    changes = {}
    # Begin background loop
    while True:
        # Store time at beginning of process
        start = t.perf_counter()
        print('Running')

        # Get users and links collections
        users = mongo.zoom_opener.login
        links = mongo.zoom_opener.links

        # Loop through stored changes and update database
        for document, change in changes.items():
            links.find_one_and_update({'username': document[0], 'id': int(document[1])}, {'$set': change})

        # Get current time
        time = datetime.datetime.utcnow()

        # Create search query for links for current time
        # Get otps and anonymous tokens
        if os.environ.get('IS_HEROKU') == 'true':
            links_search = {'active': 'true', 'activated': 'true',
                            'time': f'{int(time.strftime("%H"))}:{time.strftime("%M")}'}
            otps = mongo.zoom_opener.otp.find()
            anonymous_token = mongo.zoom_opener.anonymous_token.find()

        else:
            links_search = {'username': 'setharaphael7@gmail.com',
                            'time': f'{int(time.strftime("%H"))}:{time.strftime("%M")}'}
            otps = mongo.zoom_opener.otp.find({'email': 'setharaphael7@gmail.com'})
            anonymous_token = []

        # Iterate through possible text times
        for i in ["5", "10", "15", "20", "30", "45", "60"]:
            # Calculate time at which the link will open if a text is sent now
            future_time = datetime.datetime.utcnow() + datetime.timedelta(minutes=int(i))

            # Create search query for links for that time
            if os.environ.get('IS_HEROKU') == 'false':
                text_search = {
                    'username': 'setharaphael7@gmail.com', 'active': 'true', 'activated': 'true',
                    'time': f'{int(future_time.strftime("%H"))}:{future_time.strftime("%M")}', 'text': i
                }
            else:
                text_search = {
                    'active': 'true', 'activated': 'true',
                    'time': f'{int(future_time.strftime("%H"))}:{future_time.strftime("%M")}', 'text': i
                }
            # Iterate through all links that match the search query
            for document in links.find(text_search):
                # Get user and set default value
                user = users.find_one({"username": document['username']})
                if user is None:
                    user = {}

                # Verify the user has a phone number, the day of the week is correct, and the link is set for this week
                if dict(user).get('number') and time.strftime('%a') in document['days'] and not document.get('starts'):
                    # Send text via request to linkjoin.xyz/send_message
                    print(f'Sending text to {user["username"]} for {document["name"]}')
                    data = {'id': document['id'], 'number': user['number'], 'active': document['active'],
                            'name': document['name'], 'text': document['text'], 'key': os.environ.get('TEXT_KEY')}
                    response = requests.post("https://linkjoin.xyz/send_message", json=data,
                                             headers={'Content-Type': 'application/json'})
                    print(response)
                    print(response.text)

        # Iterate through all links that match the search query
        for document in links.find(links_search):
            # Check if the link is set to repeat by looking at first character of repeat field
            if document['repeat'][0].isdigit():
                # Some brilliant code that I don't understand
                accept = [int(document['repeat'][0]) * len(document['days']) + x - len(document['days']) + 1
                          for x in
                          range(len(document['days']))]

                if int(document['occurrences']) == accept[-1]:
                    changes[(document['username'], document['id'])] = {'occurrences': 0}
                else:
                    changes[(document['username'], document['id'])] = {
                        'occurrences': int(document['occurrences']) + 1}
                    continue

        # Create dictionary to store changes for group write to database
        edit = {}
        # Iterate through all otps
        for document in otps:
            # Check if the otp has expired
            if document['time'] - 1 == 0:
                edit[document['pw']] = {'type': 'delete'}
            else:
                edit[document['pw']] = {'type': 'edit', 'content': {'$set': {'time': document['time'] - 1}}}

        for otp, change in edit.items():
            if change['type'] == 'edit':
                mongo.zoom_opener.otp.find_one_and_update({'pw': otp}, change['content'])
            elif change['type'] == 'delete':
                mongo.zoom_opener.otp.find_one_and_delete({'pw': otp})
        edit = {}
        changed = 0
        for document in anonymous_token:
            if document.get('time'):
                if document['time'] - 1 == 0:
                    edit[document['token']] = {'type': 'delete'}
                else:
                    edit[document['token']] = {'type': 'edit', 'content': {'$set': {'time': document['time'] - 1}}}
                changed += 1
            else:
                changed += 1
                edit[document['token']] = {'type': 'edit', 'content': {'$set': {'time': 59}}}
        print(changed)
        for token, change in edit.items():
            if change['type'] == 'edit':
                mongo.zoom_opener.anonymous_token.find_one_and_update({'token': token}, change['content'])
            elif change['type'] == 'delete':
                mongo.zoom_opener.anonymous_token.find_one_and_delete({'token': token})

        if os.environ.get('IS_HEROKU') == 'true':
            print('Checking days')
            if int(mongo.zoom_opener.new_analytics.find_one({'id': 'day'})['value']) != int(time.strftime('%d')):
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'day'}, {'$set': {'value': int(time.strftime('%d'))}})
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'daily_users'}, {'$push': {'value': []}})
            if int(mongo.zoom_opener.new_analytics.find_one({'id': 'month'})['value']) != int(time.strftime('%m')):
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'month'}, {'$set': {'value': int(time.strftime('%m'))}})
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'monthly_users'}, {'$push': {'value': []}})
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'total_monthly_logins'}, {'$push': {'value': 0}})
                mongo.zoom_opener.new_analytics.find_one_and_update({'id': 'total_monthly_signups'}, {'$push': {'value': 0}})


        speed = t.perf_counter() - start
        if speed > 10:
            print(f'Long time: {speed}')
        print(speed)
        t.sleep(60-speed)


message()
