from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from visualizer.models import ObservationSet, ObsHeader
from django.db.models import fields, ManyToOneRel, Q

specialTerms = ["page"]

# Finds the character used to represent that field's class.
def type_code_for_class(field) -> str:
    type_code = "s"
    match field.__class__:
        case fields.CharField | fields.TextField:
            type_code = "s"
        case fields.IntegerField | fields.FloatField | fields.BigAutoField | fields.BigIntegerField | fields.related.ForeignKey:
            type_code = "n"
        case fields.DateTimeField:
            type_code = "d"
        case fields.BooleanField:
            type_code = "b"
    return type_code

# The operations available for the data types.
# The dictionary has the "type code"/class character for a key and a dictionary for a value.
# The type's dictionary has the operation's character as a key and a list containing: 
#       the operation name, the django expression bit and if it should be inverted/negated as it's value.
operations = {
    "s": {
        "m": ["matches", "iexact", False],
        "c": ["contains", "contains", False],
        "l": ["starts with", "startswith", False],
        "g": ["ends with", "endswith", False],
        "e": ["does not contain", "exact", True],
    },
    "n": {
        "m": ["matches", "exact", False],
        "g": ["greater than", "gt", False],
        "l": ["lesser than", "lt", False],
        "n": ["is not", "exact", True],
    },
    "d": {
        "m": ["matches", "exact", False],
        # within 24h
        "b": ["before", "lt", False],
        "a": ["after", "gt", False],
        "n": ["is not", "exact", True],
    },
    "b": {
        "i": ["is", "exact", False],
        "n": ["is not", "exact", True],
    },
}
# Create the bit of operations that will be passed to the client as a JSON object.
operationsJSON = '['
for var_type in operations:
    operationsJSON += '{"id":"'+var_type+'","values":['
    for operation_id in operations[var_type]:
        operationsJSON += '{"id":"'+operation_id+'","name":"'+operations[var_type][operation_id][0]+'"},'
    operationsJSON = operationsJSON[:-1] + ']},'
operationsJSON = operationsJSON[:-1] + ']'

# The groups with all the fields.
# The key is the identifier of the group, the value is a list with the Models class and it's name.
groups = {
    "set":[ObservationSet,"Set"],
    "header":[ObsHeader,"Header"],
}
# Make the JSON object for all the groups and their fields.
# Each group has an id, a name, and values.
# The values each have an id and a type (same as the operation types.)
fieldsJSON = '['
for group in groups:
    fieldsJSON += '{"id":"'+group+'","name":"'+groups[group][1]+'","values":['
    for field in groups[group][0]._meta.get_fields():
        if (not isinstance(field, ManyToOneRel)):
            fieldsJSON += '{"id":"'+field.attname+'","type":"'+type_code_for_class(field)+'"},'
    fieldsJSON = fieldsJSON[:-1] + ']},'
fieldsJSON = fieldsJSON[:-1] + ']'

def index(request):
    return HttpResponse("Hello, you are at the index.")

def home(request):
    return render(request, "astervis/home.html")

def search(request):
    # Create the filters for the query (we're starting with just a blank one)
    filters = Q()
    # For all the parameters in the search (except for the special ones.)
    for param in request.GET:
        if param not in specialTerms:
            # Split the param into the group and it's field.
            group = param.split('.')[0]
            field = param.split('.')[1]

            # The filter key starts with the field's name, we're assuming currently that if it's not the "set" group, that model is a field of the "set" model
            key = field
            if (not group == "set") :
                key = group + "__" + key

            # The filter to use
            op = request.GET[param][0]
            # The value to filter for
            value = request.GET[param][1:]

            type_code = type_code_for_class(groups[group][0]._meta.get_field(field))
            # Add to the filter key the filter we are using
            key += "__" + operations[type_code][op][1]
            # Fix the value's formatting if it needs adjusting
            match type_code:
                case "d":
                    value = " ".join(value.split("T"))
                case "b":
                    value = True if (value == "on" or value == "true") else False

            # Add the filter, if it needs to be inverted, do that too.
            if (operations[type_code][op][2]):
                filters = filters & ~Q(**{key: value})
            else:
                filters = filters & Q(**{key: value})
    # Search
    obss = ObservationSet.objects.filter(filters).order_by("dt")

    # How many entries to show per page
    perPage = 50
    # What page to display
    try:
        pageN = int(request.GET["page"])
    except:
        pageN = 1 # Default

    context = {"observation_list": obss[(pageN-1)*perPage:pageN*perPage],
               "fields": fieldsJSON,
               "ops": operationsJSON,
               "obs_len": obss.__len__(),
               "page": pageN,
               "tot_pages": (obss.__len__() // perPage) + 1}
    return render(request, "astervis/search.html", context)