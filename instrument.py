import csv
import os
import subprocess
import numpy as np


from datetime import datetime
from netCDF4 import Dataset
from urllib.request import urlopen
import codecs

class AMFInstrument:
    """
    Parent class for AMF instruments with common functions
    """
    amf_variables_file = None
    amfvars = {}
    timeformat = '%Y%m%d%H%M%S'
    attribtimeformat = '%Y-%m-%dT%H:%M:%S'

    @staticmethod
    def arguments():
        """
        Processes command-line arguments, returns parser.
        """
        from argparse import ArgumentParser
        parser=ArgumentParser()
        parser.add_argument('--metadata', action='append', help="Metadata filename, can be specified multiple times. Processed in order so later files override earlier ones")
        parser.add_argument('infiles',nargs='+', help="Data files to process" )
        parser.add_argument('--outdir', help="Specify directory in which output has to be created.", default="netcdf")
    
        return parser

    def __init__(self, metadatafiles, output_dir = './netcdf'):
        self.base_time = datetime(1970,1,1,0,0,0)
        self.output_dir = output_dir

        #get common attributes
        self.amfvars = self.read_amf_variables(self.amf_variables_file)
        self.raw_metadata = self.get_metadata(metadatafiles)
        if 'instrument_name' in self.raw_metadata:
            self.instrument_name = self.raw_metadata['instrument_name'][0]
            self.raw_metadata.pop('instrument_name')


    def read_amf_variables(self, csv_var_file=None):
        """
        Reads an AMF data project variable list into a structure. If 
        ``csv_var_file`` is set, read that, else calculate the TSV path from 
        the product name
        """
        out = {}
        if(csv_var_file):
            #local variable file
            varfile = csv.DictReader(open(csv_var_file,'r'))
        else:
            #get it from github
            varurl = "https://raw.githubusercontent.com/ncasuk/AMF_CVs/master/product-definitions/tsv/" + self.product + "/variables-specific.tsv"
            resource = urlopen(varurl)
            varfile = csv.DictReader(codecs.iterdecode(resource,resource.headers.get_content_charset()), delimiter="\t")
                
        for line in varfile:
            if len(line['Variable']) >0:
                out[line['Variable']] = {}
                current_var = line['Variable']
            else:
                out[current_var][line['Attribute']] = line['Value']

        return out

    def amf_var_to_netcdf_var(self, varname):
        tempvar = self.dataset.createVariable(self.amfvars[varname]['name'], self.amfvars[varname]['type'], dimensions=([x.strip() for x in self.amfvars[varname]['dimension'].split(',')]), fill_value = self.amfvars[varname]['_FillValue'])
        tempvar.long_name = self.amfvars[varname]['long_name']
        tempvar.units = self.amfvars[varname]['units']
        tempvar.coordinates = self.amfvars[varname]['coordinates']
        tempvar.cell_methods = self.amfvars[varname]['cell_methods']
        tempvar.dimension = self.amfvars[varname]['dimension']
        tempvar.type = self.amfvars[varname]['type']
        if(self.amfvars[varname]['standard_name']):
            tempvar.standard_name = self.amfvars[varname]['standard_name']

        return tempvar



    def get_metadata(self, metafiles = ['meta-data.csv']):
        raw_metadata = {} #empty dict
        for metafile in metafiles:
            with open(metafile, 'rt') as meta:
                metaread = csv.reader(meta)
                for row in metaread:
                    if len(row) == 2 and row[0] != 'Variable':
                        raw_metadata[row[0]] = row[1:]
        return raw_metadata


    def filename(self, data_product, version=1):
        """
        creates a correctly-formed AMF filename for the output netcdf file

        :param data_product: String of AMF Data Product name, e.g. ``surface_met``, ``o3_concentration``, etc. from the Product Definition Spreadsheets.
        :param version: Version of the output netCDF file. Defaults to 1. Must be convertible to a string.

        """
        file_elements = [
                self.instrument_name,
                self.raw_metadata['platform_name'][0],
                self.time_coverage_start,
                data_product,
                'v' + str(version)
                ]
        self.outfile = "_".join(file_elements) + '.nc'
        return self.outfile

    def add_standard_time(self):
        """
        Adds a standard time dimension and variable. Assumes ``self.rawdata`` is 
        a Pandas Dataframe with a Timeseries as an index.

        Adds time_coverage_start and time_coverage_end 
        as Global Attributes to the netCDF dataset
        """
        # Create the time dimension - with unlimited length
        time_dim = self.dataset.createDimension("time", None)
    
        # Create the time variable
        self.rawdata['timeoffsets'] = (self.rawdata.index - self.base_time).total_seconds()
    
        time_units = "seconds since " + self.base_time.strftime('%Y-%m-%d %H:%M:%S')
        time_var = self.dataset.createVariable("time", np.float64, dimensions=("time",))
        time_var.units = time_units
        time_var.axis = 'T'
        time_var.standard_name = "time"
        time_var.long_name = "Time (%s)" % time_units
        time_var.calendar = "standard"
        time_var.type = "float64"
        time_var.dimension = "time"
        time_var[:] = self.rawdata.timeoffsets.values
        #add global attributes
        self.dataset.time_coverage_start = self.rawdata.index[0].strftime(self.attribtimeformat)
        self.dataset.time_coverage_end = self.rawdata.index[-1].strftime(self.attribtimeformat)



    def setup_dataset(self, product, version):
        """
        instantiates NetCDF output
        """
        self.dataset = Dataset(os.path.join(self.output_dir, self.filename(product, version)), "w", format="NETCDF4_CLASSIC")

        #Processing Software attributes
        self.dataset.processing_software_url = subprocess.check_output(["git", "remote", "-v"]).split()[1]#
        self.dataset.processing_software_url = self.dataset.processing_software_url.replace('git@github.com:','https://github.com/') # get the git repository URL
        self.dataset.processing_software_version = subprocess.check_output(['git','rev-parse', '--short', 'HEAD']).strip() #record the Git revision
    
        self.add_standard_time()


    def land_coordinates(self):

        #create the location dimensions - length 1 for stationary devices
        lat  = self.dataset.createDimension('latitude', 1)
        lon  = self.dataset.createDimension('longitude', 1)
    
        #create the location variables
        latitudes = self.dataset.createVariable('latitude', np .float32,  dimensions=('latitude',))
        latitudes.units = 'degrees_north'
        latitudes.standard_name = 'latitude'
        latitudes.long_name = 'Latitude'
        latitudes.type = 'float32'
        latitudes.dimension = 'latitude'
    
        longitudes = self.dataset.createVariable('longitude', np .float32,  dimensions=('longitude',))
        longitudes.units = 'degrees_east'
        longitudes.standard_name = 'longitude'
        longitudes.long_name = 'Longitude'
        longitudes.type = 'float32'
        longitudes.dimension = 'longitude'
    
        longitudes[:] = [self.raw_metadata['platform_longitude']]
        latitudes[:] = [self.raw_metadata['platform_latitude']]
    
        #remove lat/long
        self.raw_metadata.pop('platform_longitude',None)
        self.raw_metadata.pop('platform_latitude',None)

