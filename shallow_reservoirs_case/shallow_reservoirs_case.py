import mapoperator as mo
import pandas as pd
from pathlib import Path

# ------------------------INPUT--------------------------------------
#  Raw data input path
data_A = "hexagon_experiment.csv"
data_B = "hexagon_simulation.csv"
attribute = 'dz'

name_map_A = "hexagon_exp_01_cubic"
name_map_B = "hexagon_sim_01_cubic"

#  Raster Resolution: Change as appropriate
#  NOTE: Fuzzy Analysis has unique resolution
res = 0.1

# Projection
crs = 'EPSG:4326'
nodatavalue = -9999
interpol_method = 'cubic'
# -----------------------------------------------------------------------

# Create directories if not existent
dir = Path.cwd()
Path(dir / "shapefiles").mkdir(exist_ok=True)
Path(dir / "rasters").mkdir(exist_ok=True)

if '.' not in data_A[-4:]:
    data_A += '.csv'
path_A = str(dir / "raw_data/") + "/" + data_A

if '.' not in data_B[-4]:
    data_A += '.csv'
path_B = str(dir / "raw_data/") + "/" + data_B

map_A = mo.SpatialField(name_map_A, pd.read_csv(path_A, skip_blank_lines=True), attribute=attribute, crs=crs,
                        project_dir=dir, nodatavalue=nodatavalue, res=res)
_arrayA = map_A.norm_array(method=interpol_method)
out_A = str(dir / "rasters/") + "/" + name_map_A + ".tif"
map_A.array2raster(_arrayA, out_A)


map_B = mo.SpatialField(name_map_B, pd.read_csv(path_B, skip_blank_lines=True), attribute=attribute, crs=crs,
                        project_dir=dir, nodatavalue=nodatavalue, res=res)
_arrayB = map_B.norm_array(method=interpol_method)
out_B = str(dir / "rasters/") + "/" + name_map_B + ".tif"
map_B.array2raster(_arrayB, out_B)
