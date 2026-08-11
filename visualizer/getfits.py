import ftputil
import astropy.io.fits as FITS
from django.db.models import signals
from io import BytesIO
from visualizer.models import ObservationSet, ObsLocation, ObsHeader
import threading
import time
import datetime

class ObsType:
    RAW = ".fits.gz"
    COR = "_cor.fits.gz"
    CORD = "_cord.fits.gz"

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

# Searches the location and finds all sets.
def all_from_site(location:ObsLocation):
    print("Location requested: "+location.__str__())
    with ftputil.FTPHost(location.domain, "anonymous", "") as ftp:
        all_sets = get_from_path(ftp, location.domain, location.s_path)

    save_sets(all_sets, location)

# Finds all the sets in the given path.
# Calls recursively.
# Returns all the filesets that it finds.
def get_from_path(ftp:ftputil.FTPHost, domain:str, f_path:str, wait_time=0.5):
    print(f_path)
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
                fs = FileSet(f.domain, f.f_path, f.name[:-13], None, None, f)
            elif "_cor" in f.name:
                fs = FileSet(f.domain, f.f_path, f.name[:-12], None, f, None)
            else:  # It's RAW
                fs = FileSet(f.domain, f.f_path, f.name[:-8], f, None, None)
            
            sets.append(fs)

    return sets

# Creates an ObservationSet entry for each set given.
def save_sets(sets, location:ObsLocation):
    for s in sets:
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
            saved=False,
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
        with FITS.open("ftp://" + obs_set.location.domain + obs_set.f_path + "/" + obs_set.name + obs_type, use_fsspec=True, memmap=False) as hdul:
            header = hdul[0].header
        obs = create_header(header)
        obs.save()
        obs_set.header = obs
        obs_set.save()

# Streams the desired file/observation
def stream_file(obs_set:ObservationSet, obs_type:ObsType) -> BytesIO:
    with ftputil.FTPHost(obs_set.location.domain, "anonymous", "") as ftp:
        with ftp.open(obs_set.f_path + "/" + obs_set.name + obs_type, mode="rb") as ftp_file:
            fs = BytesIO(ftp_file.read())
    fs.seek(0)
    return fs

# Creates a ObsHeader from the raw header.
# Does not save it.
def create_header(header) -> ObsHeader:
    return ObsHeader(
        bitpix = header['BITPIX'],
        naxis = header['NAXIS'],
        naxis1 = header['NAXIS1'],
        naxis2 = header['NAXIS2'],
        extend = header['EXTEND'],
        bscale = header['BSCALE'],
        bzero = header['BZERO'],
        # Image
        biassec = header['BIASSEC'],
        trimsec = header['TRIMSEC'],
        datasec = header['DATASEC'],
        ccdsec = header['CCDSEC'],
        gain = header['GAIN'],
        rdnoise = header['RDNOISE'],
        filter = header['FILTER'],
        waveleng = header['WAVELENG'],
        bandpass = header['BANDPASS'],
        xbinning = header['XBINNING'],
        ybinning = header['YBINNING'],
        compr_al = header['COMPR_AL'],
        comp_set = header['COMP_SET'],
        n_subimg = header['N_SUBIMG'],
        overscan = header['OVERSCAN'],
        creator = header['CREATOR'],
        telescop = header['TELESCOP'],
        shutter = header['SHUTTER'],
        shut_age = header['SHUT_AGE'],
        detector = header['DETECTOR'],
        # Timing
        timesys = header['TIMESYS'],
        exposure = header['EXPOSURE'],
        aexptime = header['AEXPTIME'],
        rexptime = header['REXPTIME'],
        date_obs = header['DATE-OBS'],
        time_obs = header['TIME-OBS'],
        r_exp_s = header['R_EXP_S'],
        a_exp_s = header['A_EXP_S'],
        len_flu = header['LEN_FLU'],
        len_tran = header['LEN_TRAN'],
        len_read = header['LEN_READ'],
        len_proc = header['LEN_PROC'],
        lendelay = header['LENDELAY'],
        len_save = header['LEN_SAVE'],
        # Pointing
        equinox = header['EQUINOX'],
        mode = header['MODE'],
        modetime = header['MODETIME'],
        cmd = header['CMD'],
        cmdra = header['CMDRA'],
        cmddec = header['CMDDEC'],
        cmdrol = header['CMDROL'],
        cmdq0 = header['CMDQ0'],
        cmdq1 = header['CMDQ1'],
        cmdq2 = header['CMDQ2'],
        cmdq3 = header['CMDQ3'],
        ra = header['RA'],
        dec = header['DEC'],
        objctra = header['OBJCTRA'],
        objctdec = header['OBJCTDEC'],
        objctrol = header['OBJCTROL'],
        ela_min = header['ELA_MIN'],
        ela_max = header['ELA_MAX'],
        ela_ang = header['ELA_ANG'],
        sun_min = header['SUN_MIN'],
        sun_max = header['SUN_MAX'],
        hist_nb = header['HIST_NB'],
        avg_vel = header['AVG_VEL'],
        ra_vel = header['RA_VEL'],
        dec_vel = header['DEC_VEL'],
        rol_vel = header['ROL_VEL'],
        # Environment Data
        temp_ccd = header['TEMP_CCD'],
        ccdt_nb = header['CCDT_NB'],
        temp_roe = header['TEMP_ROE'],
        temp_amp = header['TEMP_AMP'],
        temp_pld = header['TEMP_PLD'],
        # Mission Planning Section
        object = header['OBJECT'],
        observer = header['OBSERVER'],
        intent = header['INTENT'],
        instrume = header['INSTRUME'],
        targtype = header['TARGTYPE'],
        prop_id = header['PROP_ID'],
        pi_name = header['PI_NAME'],
        title = header['TITLE'],
        moving = header['MOVING'],
        m2 = header['M2'],
        geo_lat = header['GEO_LAT'],
        geo_long = header['GEO_LONG'],
        # Diagnostic
        imgstate = header['IMGSTATE'],
        # Calibration
        archive = header['ARCHIVE'],
        obs_type = header['OBSTYPE'],
        obs_id = header['OBS_ID'],
    )
        
