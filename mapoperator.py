try:
    import geopandas
    import ogr
    import gdal
    import rasterio as rio
    import numpy as np
    import pandas as pd
    import math
    from pathlib import Path
    from pyproj import CRS
    from scipy import interpolate
except:
    print('ModuleNotFoundError: Missing fundamental packages (required: geopandas, ogr, gdal, rasterio, numpy, '
          'pandas, pathlib, math, pyproj and scipy).')


class SpatialField:
    def __init__(self, name_dataset, pd, attribute, crs, project_dir, nodatavalue):
        self.pd = pd
        if not isinstance(name_dataset, str):
            print("ERROR: name_dataset must be a string")
        if not isinstance(attribute, str):
            print("ERROR: attribute must be a string, check the name on your textfile")
        self.name = name_dataset
        self.project_dir = project_dir
        self.raster = str(project_dir / "rasters") + "/" + self.name + ".tif"
        self.normraster = str(project_dir / "rasters") + "/" + self.name + "_norm.tif"
        self.norm_ascii = str(project_dir / "rasters") + "/" + self.name + "_norm.asc"
        self.crs = CRS(crs)
        self.attribute = attribute
        self.nodatavalue = nodatavalue

        # Standardize the dataframe
        self.pd.dropna(how='any', inplace=True, axis=0)
        # Create the dictionary with new label names and then rename for standardization
        new_names = {self.pd.columns[0]: 'x', self.pd.columns[1]: 'y', self.pd.columns[2]: self.attribute}
        self.pd = self.pd.rename(columns=new_names)

        # Create geodataframe from the dataframe
        gdf = geopandas.GeoDataFrame(self.pd, geometry=geopandas.points_from_xy(self.pd.x, self.pd.y))
        gdf.crs = self.crs
        self.gdf = gdf
        self.x = gdf.geometry.x.values
        self.y = gdf.geometry.y.values
        self.z = gdf[attribute].values

    def points_to_grid(self):
        """ Create a grid of new points in the desired resolution to be interpolated
        :return: array of size nrow, ncol
        http://chris35wills.github.io/gridding_data/
        """
        hrange = ((self.ymin, self.ymax),
                  (self.xmin, self.xmax))  # any points outside of this will be condisdered outliers and not used

        zi, yi, xi = np.histogram2d(self.y, self.x, bins=(int(self.nrow), int(self.ncol)), weights=self.z, normed=False,
                                    range=hrange)
        counts, _, _ = np.histogram2d(self.y, self.x, bins=(int(self.nrow), int(self.ncol)), range=hrange)
        np.seterr(divide='ignore', invalid='ignore')  # we're dividing by zero but it's no big deal
        zi = np.divide(zi, counts)
        np.seterr(divide=None, invalid=None)  # we'll set it back now
        zi = np.ma.masked_invalid(zi)
        array = np.flipud(np.array(zi))

        return array

    def norm_array(self, res=None, ulc=(np.nan, np.nan), lrc=(np.nan, np.nan), method='linear'):
        """ Normalizes the raw data in equally sparsed points depending on the selected resolution
        :return: interpolated and normalized array with selected resolution
        https://github.com/rosskush/skspatial
        """
        if np.isfinite(ulc[0]) and np.isfinite(lrc[0]):
            self.xmax = lrc[0]
            self.xmin = ulc[0]
            self.ymax = ulc[1]
            self.ymin = lrc[1]
        else:
            self.xmax = self.gdf.geometry.x.max()
            self.xmin = self.gdf.geometry.x.min()
            self.ymax = self.gdf.geometry.y.max()
            self.ymin = self.gdf.geometry.y.min()

        self.extent = (self.xmin, self.xmax, self.ymin, self.ymax)

        if np.isfinite(res):
            self.res = res
        else:
            # if res not passed, then res will be the distance between xmin and xmax / 1000
            self.res = (self.xmax - self.xmin) / 1000

        self.ncol = int(np.ceil((self.xmax - self.xmin) / self.res))  # delx
        self.nrow = int(np.ceil((self.ymax - self.ymin) / self.res))  # dely

        array = self.points_to_grid()
        x = np.arange(0, self.ncol)
        y = np.arange(0, self.nrow)

        # mask invalid values
        array = np.ma.masked_invalid(array)
        xx, yy = np.meshgrid(x, y)

        # get only the valid values
        x1 = xx[~array.mask]
        y1 = yy[~array.mask]
        newarr = array[~array.mask]
        GD1 = interpolate.griddata((x1, y1), newarr.ravel(), (xx, yy), method=method, fill_value=self.nodatavalue)

        return GD1

    def shape(self):
        self.shapefile = str(self.project_dir / 'shapefiles') + "/" + self.name + ".shp"
        self.gdf.to_file(self.shapefile)

    def plain_raster(self, res):
        """ Converts raw data to shapefile(.shp) and rasters(.tif) without normalizing
        :param res: float, resolution of the cell
        :return: no output, saves the raster in the default directory
        """
        self.shape()
        source_ds = ogr.Open(self.shapefile)
        source_layer = source_ds.GetLayer()
        x_min, x_max, y_min, y_max = source_layer.GetExtent()

        # Create Target - TIFF
        cols = int((x_max - x_min) / res)
        rows = int((y_max - y_min) / res)
        _raster = gdal.GetDriverByName('GTiff').Create(self.raster, cols, rows, 1, gdal.GDT_Float32)
        _raster.SetGeoTransform((x_min, res, 0, y_max, 0, res))
        _band = _raster.GetRasterBand(1)
        _band.SetNoDataValue(self.nodatavalue)

        # Rasterize
        gdal.RasterizeLayer(_raster, [1], source_layer, options=['ATTRIBUTE=' + self.attribute])

    def norm_raster(self, res=None, ulc=(np.nan, np.nan), lrc=(np.nan, np.nan), method='linear', save_ascii=True):
        """ Saves a raster using interpolation
        :param save_ascii:
        :param res: float, resolution of the cell
        :param ulc: tuple, upper left corner
        :param lrc: tuple, lower right corner
        :param method: interpolation method {‘linear’, ‘nearest’, ‘cubic’}, more info at: https://docs.scipy.org/doc/scipy/reference/generated/scipy.interpolate.griddata.html
        :return: no output, saves the raster in the default directory
        """
        array = self.norm_array(res=res, ulc=ulc, lrc=lrc, method=method)
        self.transform = rio.transform.from_origin(self.xmin, self.ymax, self.res, self.res)
        new_dataset = rio.open(self.normraster, 'w', driver='GTiff',
                               height=array.shape[0], width=array.shape[1], count=1, dtype=array.dtype,
                               crs=self.crs, transform=self.transform, nodata=self.nodatavalue)
        print(np.shape(array))
        new_dataset.write(array, 1)
        new_dataset.close()

        if save_ascii:
            map_asc = self.norm_ascii
            gdal.Translate(map_asc, self.normraster, format='AAIGrid')

        return new_dataset

    def create_polygon(self, shape_polygon, alpha=np.nan):
        try:
            import alphashape
            # If the user doesnt select an alpha value, the alpha will be optimized automatically.
        except ImportError as e:
            print(e)
        else:
            if np.isfinite(alpha):
                try:
                    polygon = alphashape.alphashape(self.gdf, alpha)
                except FileNotFoundError as e:
                    print(e)
            else:
                try:
                    polygon = alphashape.alphashape(self.gdf)
                except FileNotFoundError as e:
                    print(e)
                else:
                    polygon.crs = self.crs
                    polygon.to_file(shape_polygon)

    def clip_raster(self, polygon, out_raster):
        import earthpy.spatial as es
        import earthpy.plot as ep
        from rasterio import plot
        import matplotlib.pyplot as plt

        # Read the raster to be cropped
        with rio.open(self.normraster, count=1) as src:
            # Read the shapefile
            crop_extent = geopandas.read_file(polygon)
            crop_extent = crop_extent.to_crs(src.crs)

            # Crop the raster
            raster_crop, raster_meta = es.crop_image(src, crop_extent, all_touched=True)
        raster_meta.update({'transform': raster_meta["transform"],
                            'height': raster_crop.shape[1],
                            'width': raster_crop.shape[2],
                            'nodata': self.nodatavalue})

        print(raster_meta["transform"])

        raster_plot = plot.plotting_extent(raster_crop[0], raster_meta["transform"])

        print(raster_crop[0])
        fig, ax = plt.subplots(figsize=(12, 6))

        # Plot the shapefile
        crop_extent.boundary.plot(ax=ax, color="red", zorder=10)

        # Plot the raster
        ep.plot_bands(
            raster_crop[0],
            ax=ax,
            extent=raster_plot,
            title="test", cmap='Greys')
        plt.show()

        # Save the raster
        with rio.open(out_raster, 'w', **raster_meta) as outf:
            outf.write(raster_crop[0].astype(rio.float64), 1)


class MapArray:
    def __init__(self, map_name, raster):
        self.map_name = map_name
        self.raster = raster

        with rio.open(self.raster) as src:
            raster_np = src.read(1, masked=True)
            self.nodatavalue = src.nodata  # storing nodatavalue of raster
            self.meta = src.meta.copy()
        self.array = raster_np

    def nb_classes(self, n_classes):
        """ Class bins based on the Natural Breaks method
            :param n_classes: integer, number of classes
            :return: list, optimized bins
        """
        try:
            import mapclassify.classifiers as mc
        except ModuleNotFoundError as e:
            print(e)
        else:
            # Classification based on Natural Breaks
            breaks = mc.NaturalBreaks(self.array.ravel(), k=n_classes + 1)
            print('The bins were optimized to:', breaks.bins)
            class_bins = breaks.bins.tolist()
            return class_bins

    def categorize_raster(self, class_bins, project_dir, save_ascii=True):
        """ Classifies the raster according to the classification bins
        :param project_dir: path of the project directory
        :param class_bins: list
        :return: no return, saves the classified raster in the chosen directory
        """
        # Classify the original image array (digitize makes nodatavalues take the class 0)
        raster_class = np.digitize(self.array, class_bins, right=True)

        # Assigns nodatavalues back to array
        raster_ma = np.ma.masked_where(raster_class == 0,
                                       raster_class,
                                       copy=True)

        # Fill nodatavalues into array
        raster_ma_fi = np.ma.filled(raster_ma, fill_value=self.nodatavalue)

        map_out = str(project_dir / "rasters/") + "/" + self.map_name + ".tif"

        if raster_ma_fi.min() == self.nodatavalue:
            with rio.open(map_out, 'w', **self.meta) as outf:
                outf.write(raster_ma_fi.astype(rio.float64), 1)
        else:
            raise TypeError("Error filling NoDataValue to raster file")

        if save_ascii:
            map_asc = str(project_dir / "rasters") + "/" + self.map_name + ".asc"
            gdal.Translate(map_asc, map_out, format='AAIGrid')


if __name__ == '__main__':
    # ------------------------INPUT--------------------------------------
    #  Raw data input path
    data_A = "hexagon_experiment.csv"
    data_B = "hexagon_simulation.csv"
    attribute = 'dz'

    name_map_A = "hexagon_exp_02"
    name_map_B = "hexagon_sim_02"

    #  Raster Resolution: Change as appropriate
    #  NOTE: Fuzzy Analysis has unique resolution
    res = 0.2

    # Projection
    crs = 'EPSG:4326'
    nodatavalue = -9999
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

    map_A = SpatialField(name_map_A, pd.read_csv(path_A, skip_blank_lines=True), attribute=attribute, crs=crs,
                         project_dir=dir, nodatavalue=nodatavalue)
    map_A.norm_raster(res, method='linear')

    map_B = SpatialField(name_map_B, pd.read_csv(path_B, skip_blank_lines=True), attribute=attribute, crs=crs,
                         project_dir=dir, nodatavalue=nodatavalue)
    map_B.norm_raster(res, method='linear')
