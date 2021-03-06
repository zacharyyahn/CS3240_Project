from django.views import generic
from django.shortcuts import render
from .forms import ScheduleForm, MakeEventForm, UpdateEventForm
import requests
import json
from .models import ClassModel, EventModel
import re
from django.contrib.auth import logout
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse
from datetime import datetime
from datetime import date

max_capacity = 999


#########################
# Reference
# Title: Django passing variables to templates from class based views
# Author: therealak12
# URL:  https://docs.mapbox.com/api/search/geocoding/
########################
class GeoCode:
    """
    Data format:
    {
    type: ...,
    query: [What you searched for],
    features: [{lots of data}]
    attribution: copyright notice. This data cannot be retained?
    }
    """

    def __init__(self, response):
        data = json.load(response)
        self.query = data.get('query')
        self.coordinates = [data.get('features')[0].get('center')[0], data.get('features')[0].get('center')[1]]
        self.name = data.get('features')[0].get('text')
        self.location = data.get('features')[0].get('place_name')

    def __init__(self, query, coordinates, name, location_name):
        self.query = query
        self.coordinates = coordinates
        self.name = name
        self.location_name = location_name

    @staticmethod
    def get_geo_codes(data):
        """ Transforms the json data into an array of GeoCodes """
        query = ' '.join(data.get('query'))
        results = data.get('features')
        output = []
        for result in results:
            coordinates = [result.get('center')[0], result.get('center')[1]]
            name = result.get('text')
            location_name = result.get('place_name')
            output.append(GeoCode(query, coordinates, name, location_name))

        return output


class SearchResult:

    def __init__(self, class_name, class_room, class_title, class_loc_coords, class_id, signed_in, in_schedule):
        self.class_name = class_name
        self.class_room = class_room
        self.class_title = class_title
        self.class_loc_coords = class_loc_coords
        self.class_id = class_id
        self.signed_in = signed_in
        if not self.signed_in:
            self.in_schedule = False
        else:
            self.in_schedule = in_schedule

    def __str__(self):
        return self.class_name


class MapView(generic.FormView):
    template_name = "map/map.html"
    form_class = ScheduleForm

    access_token = 'pk.eyJ1IjoiYS0wMiIsImEiOiJja21iMzl4dHgxeHFtMnBxc285NGMwZG5kIn0.Rl2qXrod77iHqUJ-eMbkcg'
    starting_coords = [-78.510067, 38.038124]

    #########################
    # Reference
    # Title: Django passing variables to templates from class based views
    # Author: therealak12
    # URL:  https://stackoverflow.com/questions/18232851/django-passing-variables-to-templates-from-class-based-views
    ########################
    # Makes this classes global variables accessible from the templates
    def get_context_data(self, **kwargs):
        context = super(MapView, self).get_context_data(**kwargs)
        context.update({'starting_coords': self.starting_coords, 'access_token': self.access_token})
        context['eventsList'] = EventModel.objects.all()  # created a variable that map.html can see
        return context


# Returns search results
#########################
# Reference
# Title: Local Search with the GeoCoding API
# Author:
# URL:  https://docs.mapbox.com/help/tutorials/local-search-geocoding-api/
########################
def get_search_results(query):
    # Make this not stored here...
    access_token = 'pk.eyJ1IjoiYS0wMiIsImEiOiJja21iMzl4dHgxeHFtMnBxc285NGMwZG5kIn0.Rl2qXrod77iHqUJ-eMbkcg'
    starting_coords = [-78.510067, 38.038124]

    base_url = 'https://api.mapbox.com/geocoding/v5/mapbox.places/'
    params = {'limit': 5,
              'proximity': str(starting_coords[0]) + ',' + str(starting_coords[1]),
              'bbox': '-78.526434,38.028392,-78.475622,38.055975',
              'access_token': access_token}
    # Get the data from MapBox's API
    r = requests.get(base_url + query + '.json', params=params)
    # Parse that data into a more useful form
    # print(GeoCode.get_geo_codes(r.json()))
    return GeoCode.get_geo_codes(r.json())


def parse_classes(search_input):
    """ Returns an array of the [Class number, class mnemonic, course number, class section] with None
    if that part could not be found """
    # Looks for a series of letters, followed by a series of numbers followed by another series of numbers
    result = re.search('[0-9]*\s*[a-zA-Z]*\s*[0-9]*\s*[0-9]*', search_input)
    if result:
        output = [None, None, None, None, None]
        array = result.group().split()
        for element in array:
            if element.isalpha() and 2 <= len(element) <= 4:  # This must be the mnemonic
                element = element.upper()
                mnemonic = ClassModel.objects.filter(class_mnemonic=element)
                if mnemonic.exists():
                    output[1] = element
            elif element.isalpha():  # Could be the class title
                title = ClassModel.objects.filter(class_title__icontains=element)
                if title.exists():
                    output[4] = search_input  # Possibly dangerous. The regex only gets the first word
            elif element.isnumeric():  # Must be a number
                if len(element) == 5:  # Must be the class number
                    output[0] = element
                if len(element) == 4:  # Must be the course number
                    output[2] = element
                if len(element) <= 3:  # Must be the section number
                    output[3] = element

        return output
    else:
        return [None, None, None, None, None]


def get_class_search_results(request):
    if request.method == 'POST':
        form = ScheduleForm(request.POST)  # generate the form from the data supplied

        if form.is_valid():
            query = parse_classes(form.cleaned_data['search'])
            class_number = query[0]
            class_mnemonic = query[1]
            course_number = query[2]
            class_section = query[3]
            class_title = query[4]

            if query == [None, None, None, None, None]:
                results = get_search_results(form.cleaned_data['search'])

                return render(request, 'map/locations.html', {'results': results})

            # Creates a filter chain from the results of the parsing. Should strip out
            # anything not relevant
            results = ClassModel.objects
            if class_number is not None:
                results = results.filter(class_number=class_number)
            if class_mnemonic is not None:
                results = results.filter(class_mnemonic=class_mnemonic)
            if course_number is not None:
                results = results.filter(course_number=course_number)
            if class_section is not None:
                results = results.filter(class_section=class_section)
            if class_title is not None:
                results = results.filter(class_title__icontains=class_title)

            output = []
            for r in results:
                # Don't use the search API if we know it won't return anything
                if r.class_room != 'Web-Based Course-No class mtgs' \
                        and r.class_room != 'Web-Based Course' \
                        and r.class_room != 'TBA':
                    # Searches for the building after removing any room numbers
                    search_results = get_search_results(re.sub('\d', '', r.class_room))
                    if len(search_results) != 0:
                        coords = search_results[0].coordinates
                    else:
                        coords = None
                else:
                    coords = None

                # Check if it's in the user's schedule
                user = request.user
                if user.is_authenticated:
                    in_schedule = r in user.schedule.all()
                else:
                    in_schedule = False

                output.append(
                    SearchResult(r.__str__(), r.class_room, r.class_title, coords, r.class_number,
                                 user.is_authenticated, in_schedule))
            return render(request, 'map/classes.html', {'classR': output})

    else:
        return render(request, 'map/classes.html', {'classR': []})


def add_class(request):
    if request.method == 'POST':
        class_id = request.POST.get('class-id')
        user = request.user
        if user.is_authenticated:
            class_to_add = ClassModel.objects.get(class_number=class_id)
            user.schedule.add(class_to_add)
            schedule = user.schedule.all()
            return render(request, 'map/user_schedule.html', {'schedule': schedule})

        return render(request, 'map/user_schedule.html', {'schedule': []})

    return render(request, 'map/user_schedule.html', {'schedule': []})


def remove_class(request):
    if request.method == 'POST':
        class_id = request.POST.get('class-id')
        user = request.user
        if user.is_authenticated:
            class_to_remove = ClassModel.objects.get(class_number=class_id)
            user.schedule.remove(class_to_remove)
            schedule = user.schedule.all()
            return render(request, 'map/user_schedule.html', {'schedule': schedule})

        return render(request, 'map/user_schedule.html', {'schedule': []})

    return render(request, 'map/user_schedule.html', {'schedule': []})


def check_date(event):
    currentDay = date.today()
    currentTime = datetime.now().time()

    if event.date > currentDay:
        return event.date > currentDay
    elif event.date == currentDay:
        return event.time >= currentTime
    else:
        return False


# Returns search results
#########################
# References
# Title: Working with forms
# Author:
# URL: https://docs.djangoproject.com/en/3.2/topics/forms/
########################
def user_created_event(request):
    if request.method == 'POST':
        user = request.user
        event_form = MakeEventForm(request.POST)
        if user.is_authenticated and event_form.is_valid():
            entry = event_form.save(commit=False)  # Don't save to the database just yet
            if check_date(entry) and entry.capacity <= max_capacity:
                entry.host = user  # Tie the host to this user
                # Ignore the attendees they are set later
                entry.save()  # Save to the database
                event_form.save_m2m()  # Needs to be called if commit = False
                return render(request, 'map/event.html', {'success': True, 'error': None})
            else:
                if not check_date(entry):
                    return render(request, 'map/event.html',
                                  {'success': False, 'error': 'The time must be in the future.'})
                else:
                    return render(request, 'map/event.html', {'success': False, 'error': 'Maximum capacity is 999'})
        else:
            return render(request, 'map/event.html', {'success': False, 'error': event_form.errors})

    return render(request, 'map/event.html', {'success': False, 'error': ''})


# Host can update event
def user_updated_event(request):
    if request.method == 'POST':
        user = request.user
        event_form = UpdateEventForm(request.POST)
        print("User updating event")
        if user.is_authenticated and event_form.is_valid():
            database_entry = EventModel.objects.get(pk=event_form.cleaned_data['id'])

            database_entry.title = event_form.cleaned_data['title']
            database_entry.location = event_form.cleaned_data['location']
            database_entry.date = event_form.cleaned_data['date']
            database_entry.time = event_form.cleaned_data['time']
            database_entry.capacity = event_form.cleaned_data['capacity']
            database_entry.description = event_form.cleaned_data['description']
            if check_date(database_entry) and database_entry.capacity <= max_capacity:
                database_entry.save()
                return render(request, 'map/event.html', {'success': True, 'error': None})
            else:
                if not check_date(database_entry):
                    return render(request, 'map/event.html',
                                  {'success': False, 'error': 'The time must be in the future.'})
                else:
                    return render(request, 'map/event.html', {'success': False, 'error': 'Maximum capacity is 999'})
        else:
            return render(request, 'map/event.html', {'success': False, 'error': event_form.errors})

    return render(request, 'map/event.html', {'success': False, 'error': ''})


# User can attend event
def attend_event(request):
    if request.method == 'POST':
        user = request.user
        event_id = request.POST.get('event')
        event_to_attend = EventModel.objects.get(pk=event_id)
        # checks if already attending event and if host tries to attend own event
        eventAddOne = event_to_attend.numberOfAttendees + 1
        if event_to_attend.host != user and event_to_attend not in user.attendees.all() and eventAddOne <= event_to_attend.capacity:
            user.attendees.add(event_to_attend)  # link user and event
            event_to_attend.numberOfAttendees += 1  # update attendance
            event_to_attend.save()

    return render(request, 'map/event_list.html', {'eventsList': EventModel.objects.all()})


# Host can cancel event
def cancel_event(request):
    if request.method == 'POST':
        user = request.user
        event_id = request.POST.get('event')
        event_to_attend = EventModel.objects.get(pk=event_id)
        user.attendees.remove(event_to_attend)  # unlink user and event
        if event_to_attend.numberOfAttendees > 0 and event_to_attend.host != user:
            event_to_attend.numberOfAttendees -= 1  # update attendance
        event_to_attend.save()

    return render(request, 'map/event_list.html', {'eventsList': EventModel.objects.all()})


def remove_event_from_list(request):
    if request.method == 'POST':
        event_id = request.POST.get('event')
        user = request.user
        if user.is_authenticated:
            EventModel.objects.get(pk=event_id).delete()

        return render(request, 'map/event_list.html', {'eventsList': EventModel.objects.all()})

    return render(request, 'map/event_list.html', {'eventsList': EventModel.objects.all()})


# updates Event Models that are valid in eventsList
# Returns search results
#########################
# Reference
# Title: Working with Queries
# Author:
# URL: https://docs.djangoproject.com/en/3.2/topics/db/queries/
########################
def update_event_list():
    eventsList = EventModel.objects.all()
    newEventsList = []
    for e in eventsList:
        if check_date(e) and e.capacity <= max_capacity:
            newEventsList.append(e)
        else:
            EventModel.objects.filter(id=e.id).delete()
    return newEventsList


def get_event_list(request):
    update_event_list()
    # print(EventModel.objects.all())
    return render(request, 'map/event_list.html', {'eventsList': EventModel.objects.all()})


def show_schedule_page(request):
    return render(request, 'map/schedule_page.html')


def show_events_page(request):
    update_event_list()
    # print(EventModel.objects.all())
    return render(request, 'map/events_page.html', {'eventsList': EventModel.objects.all()})


def is_class_in_schedule(request):
    if request.method == 'GET':
        class_id = request.GET.get('class-id')
        class_to_check = ClassModel.objects.get(class_number=class_id)
        user = request.user
        if user.is_authenticated and class_to_check in user.schedule.all():
            return JsonResponse({'has_class': True})

    return JsonResponse({'has_class': False})


def logout_view(request):
    #########################
    # Reference
    # Title: Using the Django authentication system
    # Author: Django
    # URL:  https://docs.djangoproject.com/en/3.2/topics/auth/default/
    ########################
    # Used to get rid of ugly logout page and redirect to home page with login
    logout(request)
    return HttpResponseRedirect(reverse('map:map'))
