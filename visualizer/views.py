from django.http import FileResponse
from django.shortcuts import render, get_object_or_404
import ftputil
from mimetypes import guess_type
from visualizer.models import ObservationSet
from visualizer import getfits

# Create your views here.

def set(request, obs_name):
    obs_set = get_object_or_404(ObservationSet, name=obs_name)
    getfits.prep_file(obs_set, getfits.ObsType.RAW)
    obs_set.refresh_from_db()
    
    context = {"set": obs_set,}
    return render(request, "visualizer/display.html", context)

def get(request, obs_name):
    obs_set = get_object_or_404(ObservationSet, name=obs_name)
    # Which observation to grab.
    match request.GET["obs"]:
        case "COR":
            obs_type = getfits.ObsType.COR
        case "CORD":
            obs_type = getfits.ObsType.CORD
        case "RAW" | _:
            obs_type = getfits.ObsType.RAW
    # Stream that observation
    content_type, encoding = guess_type(obs_set.name + obs_type)
    content_type = content_type or "application/octet-stream"
    response = FileResponse(getfits.stream_file(obs_set, obs_type), content_type=content_type)
    if encoding:
        response.headers["Content-Encoding"] = encoding
    return response