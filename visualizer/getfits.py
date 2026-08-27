import ftputil
import astropy.io.fits as FITS
from django.db.models import signals
from io import BytesIO
from visualizer.models import ObservationSet, ObsLocation, ObsHeader
import threading
import time
import datetime

status = ""

class ObsType:
    RAW = "."
    COR = "_cor."
    CORD = "_cord."

class FileRef:
    def __init__(self, domain:str, f_path:str, name:str):
        self.domain = domain
        self.f_path = f_path
        self.name = name

    def __str__(self):
        return "(" + self.f_path + " & " + self.base_name + ")"


class FileSet:
    def __init__(self, domain:str, f_path:str, base_name:str, raw:FileRef, cor:FileRef, cord:FileRef):
        self.domain = domain
        self.f_path = f_path
        self.base_name = base_name
        self.raw = raw
        self.cor = cor
        self.cord = cord
    
    def __str__(self):
        hr = ("✅", "❌")[self.raw is None]
        hc = ("✅", "❌")[self.cor is None]
        hd = ("✅", "❌")[self.cord is None]
        return "(" + self.f_path + " & " + self.base_name + " | R:" + hr + " C:" + hc + " D:" + hd + ")"

# A function that will search a location when it is added.
def on_location_added(sender, instance, created, **kwargs):
    if created: threading.Thread(target=all_from_site, args=(instance,)).start()
signals.post_save.connect(on_location_added, sender=ObsLocation)

def set_status(msg:str, log:bool=True):
    global status
    status = msg
    if (log): print(msg)

def get_status() -> str:
    return status

# Searches the location and finds all sets.
def all_from_site(location:ObsLocation):
    set_status("Location requested: "+location.__str__())
    try:
        with ftputil.FTPHost(location.domain, "anonymous", "") as ftp:
            all_sets = get_from_path(ftp, location.domain, location.s_path)

        set_status("Saving collected sets:")
        save_sets(all_sets, location)
    except Exception as error:
        set_status("Ran into error while saving from site: "+error)
    set_status("", False)

# Finds all the sets in the given path.
# Calls recursively.
# Returns all the filesets that it finds.
def get_from_path(ftp:ftputil.FTPHost, domain:str, f_path:str, wait_time=0.5):
    set_status("Retrieving from path: "+f_path)
    filesets = []
    files = []
    for elem in ftp.listdir(f_path):
        if (ftp.path.isdir(f_path+"/"+elem)):
            time.sleep(wait_time)
            filesets = filesets + get_from_path(ftp, domain, f_path+"/"+elem)
        else:
            files.append(FileRef(domain, f_path, elem))

    return filesets + sort_into_sets(files)

# Sorts files into sets.
# Expects files to be formated like: Raw:[NAME].fits.gz, Cor:[NAME]_cor.fits.gz and Cord:[NAME]_cord.fits.gz
def sort_into_sets(files):
    sets = []
    for f in files:
        found = False
        for s in sets:
            if s.base_name in f.name:
                found = True
                if "_cord" in f.name:
                    s.cord = f
                elif "_cor" in f.name:
                    s.cor = f
                else:  # Raw.
                    s.raw = f
                break
        
        if not found:
            if "_cord" in f.name:
                fs = FileSet(f.domain, f.f_path, f.name.split('.')[0][:-5], None, None, f)
            elif "_cor" in f.name:
                fs = FileSet(f.domain, f.f_path, f.name.split('.')[0][:-4], None, f, None)
            else:  # It's RAW
                fs = FileSet(f.domain, f.f_path, f.name.split('.')[0], f, None, None)
            
            sets.append(fs)

    return sets

# Creates an ObservationSet entry for each set given.
def save_sets(sets, location:ObsLocation):
    for s in sets:
        set_status("Saving: "+s.f_path+" "+s.base_name, False)
        strtime = s.base_name.split("_")[2]
        obstime = datetime.datetime(year=int(strtime[0:4]), month=1, day=1) + datetime.timedelta(days=int(strtime[4:7])-1, seconds=int(strtime[11:]), hours=int(strtime[7:9]), minutes=int(strtime[9:11]))
        r = (True, False)[s.raw is None]
        c = (True, False)[s.cor is None]
        d = (True, False)[s.cord is None]
        # If set with name already exists, overwrite it?
        obset = ObservationSet(
            name=s.base_name,
            location=location,
            f_path=s.f_path,
            dt=obstime,
            raw=r,
            cor=c,
            cord=d,
            header=None
        )
        obset.save()

# "Prepares" the file by downloading it and saving it's header.
# Will not do it if the header is already stored.
def prep_file(obs_set:ObservationSet, obs_type:ObsType, overwrite:bool=False): # ftp://data.asc-csa.gc.ca/users/OpenData_DonneesOuvertes/pub/NEOSSAT/ASTRO/2026/109/NEOS_SCI_2026109004941_cord.fits.gz
    if not obs_set.header:
        with ftputil.FTPHost(obs_set.location.domain, "anonymous", "") as ftp:
            file_name = [file for file in ftp.listdir(obs_set.f_path) if ((obs_set.name + obs_type) in file)][0]
        with FITS.open("ftp://" + obs_set.location.domain + obs_set.f_path + "/" + file_name, use_fsspec=True, memmap=False) as hdul:
            header = hdul[0].header
        obs = create_header(header)
        obs.save()
        obs_set.header = obs
        obs_set.save()

# Streams the desired file/observation
def stream_file(obs_set:ObservationSet, obs_type:ObsType) -> tuple[BytesIO, str]:
    with ftputil.FTPHost(obs_set.location.domain, "anonymous", "") as ftp:
        file_name = [file for file in ftp.listdir(obs_set.f_path) if ((obs_set.name + obs_type) in file)][0]
        with ftp.open(obs_set.f_path + "/" + file_name, mode="rb") as ftp_file:
            fs = BytesIO(ftp_file.read())
    fs.seek(0)
    return (fs, file_name)

# Creates a ObsHeader from the raw header.
# Does not save it.
def create_header(header) -> ObsHeader:
    return ObsHeader(
        bitpix = header.get('BITPIX', default=0),
        naxis = header.get('NAXIS', default=0),
        naxis1 = header.get('NAXIS1', default=0),
        naxis2 = header.get('NAXIS2', default=0),
        extend = header.get('EXTEND', default=False),
        bscale = header.get('BSCALE', default=float("nan")),
        bzero = header.get('BZERO', default=0),
        # Image
        biassec = header.get('BIASSEC', default="null"),
        trimsec = header.get('TRIMSEC', default="null"),
        datasec = header.get('DATASEC', default="null"),
        ccdsec = header.get('CCDSEC', default="null"),
        gain = header.get('GAIN', default=float("nan")),
        rdnoise = header.get('RDNOISE', default=float("nan")),
        filter = header.get('FILTER', default="null"),
        waveleng = header.get('WAVELENG', default=0),
        bandpass = header.get('BANDPASS', default="null"),
        xbinning = header.get('XBINNING', default=0),
        ybinning = header.get('YBINNING', default=0),
        compr_al = header.get('COMPR_AL', default="null"),
        comp_set = header.get('COMP_SET', default="null"),
        n_subimg = header.get('N_SUBIMG', default=0),
        overscan = header.get('OVERSCAN', default=0),
        creator = header.get('CREATOR', default="null"),
        telescop = header.get('TELESCOP', default="null"),
        shutter = header.get('SHUTTER', default="null"),
        shut_age = header.get('SHUT_AGE', default=float("nan")),
        detector = header.get('DETECTOR', default="null"),
        # Timing
        timesys = header.get('TIMESYS', default="null"),
        exposure = header.get('EXPOSURE', default=float("nan")),
        aexptime = header.get('AEXPTIME', default=float("nan")),
        rexptime = header.get('REXPTIME', default=float("nan")),
        date_obs = header.get('DATE-OBS', default=float("nan")),
        time_obs = header.get('TIME-OBS', default=float("nan")),
        r_exp_s = header.get('R_EXP_S', default=float("nan")),
        a_exp_s = header.get('A_EXP_S', default=float("nan")),
        len_flu = header.get('LEN_FLU', default=float("nan")),
        len_tran = header.get('LEN_TRAN', default=float("nan")),
        len_read = header.get('LEN_READ', default=float("nan")),
        len_proc = header.get('LEN_PROC', default=float("nan")),
        lendelay = header.get('LENDELAY', default=float("nan")),
        len_save = header.get('LEN_SAVE', default=float("nan")),
        # Pointing
        equinox = header.get('EQUINOX', default=float("nan")),
        mode = header.get('MODE', default="null"),
        modetime = header.get('MODETIME', default=float("nan")),
        cmd = header.get('CMD', default="null"),
        cmdra = header.get('CMDRA', default="null"),
        cmddec = header.get('CMDDEC', default="null"),
        cmdrol = header.get('CMDROL', default=float("nan")),
        cmdq0 = header.get('CMDQ0', default=float("nan")),
        cmdq1 = header.get('CMDQ1', default=float("nan")),
        cmdq2 = header.get('CMDQ2', default=float("nan")),
        cmdq3 = header.get('CMDQ3', default=float("nan")),
        ra = header.get('RA', default="null"),
        dec = header.get('DEC', default="null"),
        objctra = header.get('OBJCTRA', default="null"),
        objctdec = header.get('OBJCTDEC', default="null"),
        objctrol = header.get('OBJCTROL', default=float("nan")),
        ela_min = header.get('ELA_MIN', default=float("nan")),
        ela_max = header.get('ELA_MAX', default=float("nan")),
        ela_ang = header.get('ELA_ANG', default=float("nan")),
        sun_min = header.get('SUN_MIN', default=float("nan")),
        sun_max = header.get('SUN_MAX', default=float("nan")),
        hist_nb = header.get('HIST_NB', default=0),
        avg_vel = header.get('AVG_VEL', default=float("nan")),
        ra_vel = header.get('RA_VEL', default=float("nan")),
        dec_vel = header.get('DEC_VEL', default=float("nan")),
        rol_vel = header.get('ROL_VEL', default=float("nan")),
        # Environment Data
        temp_ccd = header.get('TEMP_CCD', default=float("nan")),
        ccdt_nb = header.get('CCDT_NB', default=0),
        temp_roe = header.get('TEMP_ROE', default=float("nan")),
        temp_amp = header.get('TEMP_AMP', default=float("nan")),
        temp_pld = header.get('TEMP_PLD', default=float("nan")),
        # Mission Planning Section
        object = header.get('OBJECT', default="null"),
        observer = header.get('OBSERVER', default="null"),
        intent = header.get('INTENT', default="null"),
        instrume = header.get('INSTRUME', default="null"),
        targtype = header.get('TARGTYPE', default="null"),
        prop_id = header.get('PROP_ID', default="null"),
        pi_name = header.get('PI_NAME', default="null"),
        title = header.get('TITLE', default="null"),
        moving = header.get('MOVING', default="null"),
        m2 = header.get('M2', default="null"),
        geo_lat = header.get('GEO_LAT', default="null"),
        geo_long = header.get('GEO_LONG', default="null"),
        # Diagnostic
        imgstate = header.get('IMGSTATE', default="null"),
        # Calibration
        archive = header.get('ARCHIVE', default="null"),
        obs_type = header.get('OBSTYPE', default="null"),
        obs_id = header.get('OBS_ID', default="null"),
    )
        
