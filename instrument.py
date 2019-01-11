import csv

class AMFInstrument:
    """
    Parent class for AMF instruments with common functions
    """

    def init(self, input_file, metadatafile, outfile = None):
        #get common attributes
        self.comattrs = self.read_amf_variables(metadatafile)
    

    def read_amf_variables(self, csv_var_file):
        """
        Reads an AMF data project CSV-format variable list into a structure.
        """
        out = {}
        with open(csv_var_file,'r') as f:
            varfile = csv.DictReader(f)
            for line in varfile:
                if len(line['Variable']) >0:
                    out[line['Variable']] = {}
                    current_var = line['Variable']
                else:
                    out[current_var][line['Attribute']] = line['Value']

        return out

    def arguments(self):
        """
        Processes command-line arguments, returns parser.
        """
        from argparse import ArgumentParser
        parser=ArgumentParser()
        parser.add_argument('--outfile', dest="output_file", help="NetCDF output filename", default='sonic_2d_data.nc')
        parser.add_argument('--metadata', dest="metadata", help="Metadata filename", default='2d-sonic-metadata')
        parser.add_argument('infiles',nargs='+', help="Gill 2D Windsonic data files" )
        parser.add_argument('--outdir', help="Specify directory in which output has to be created.", default="netcdf")
    
        return parser

    def filename(self, variable, version):
        """
        creates a correctly-formed AMF filename for the output netcdf file
        """
        file_elements = [
                self.instrument_name,
                self.raw_metadata['platform_name'][0],
                time_coverage_start,
                variable,
                'v' + version 
                ]
        self.outfile = "_".join(file_elements) + '.nc'

