# -*- coding: utf-8 -*-


#
# * Copyright (c) 2009-2015. Authors: see NOTICE file.
# *
# * Licensed under the Apache License, Version 2.0 (the "License");
# * you may not use this file except in compliance with the License.
# * You may obtain a copy of the License at
# *
# *      http://www.apache.org/licenses/LICENSE-2.0
# *
# * Unless required by applicable law or agreed to in writing, software
# * distributed under the License is distributed on an "AS IS" BASIS,
# * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# * See the License for the specific language governing permissions and
# * limitations under the License.
# */


__author__          = "Stévens Benjamin <b.stevens@ulg.ac.be>" 
__contributors__    = ["Marée Raphaël <raphael.maree@ulg.ac.be>"]                
__copyright__       = "Copyright 2010-2015 University of Liège, Belgium, http://www.cytomine.be/"



import os, sys, time
import optparse
import cv
import pickle

from cytomine import Cytomine
from cytomine_utilities.filter import AdaptiveThresholdFilter, BinaryFilter, OtsuFilter
from cytomine_utilities.objectfinder import ObjectFinder
from cytomine_utilities.reader import Bounds, CytomineReader
from cytomine_utilities.utils import Utils
from cytomine_utilities.wholeslide import WholeSlide

__author__ = 'stevben'

class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

def main(argv):
    # modes
    modes = Enum(['MANUAL','AUTO'])

    #filter
    filters = { 'binary' : BinaryFilter(), 'adaptive' : AdaptiveThresholdFilter(), 'otsu' : OtsuFilter()}

    parser = optparse.OptionParser(description='Cytomine Datamining',
                              prog='cytomining',
                              version='cytomining 0.1')
    parser.add_option('-m', '--mode', dest='mode', type = 'choice', choices = [modes.MANUAL, modes.AUTO], help = 'manual or auto mode')
    parser.add_option('-i', '--image', type='int', dest='id_image',
                  help='image id from cytomine', metavar='IMAGE')
    parser.add_option('--cytomine_host', dest='cytomine_host', help='cytomine_host')
    parser.add_option('--cytomine_public_key', dest='cytomine_public_key', help='cytomine_public_key')
    parser.add_option('--cytomine_private_key', dest='cytomine_private_key', help='cytomine_private_key')
    parser.add_option('--cytomine_base_path', dest='cytomine_base_path', help='cytomine base path')
    parser.add_option('--cytomine_working_path', dest='cytomine_working_path', help='cytomine_working_path base path')
    parser.add_option('--cytomine_publish', action="store_true", default=False, dest="publish_annotations", help="Turn on upload of geometries")
    parser.add_option('--zoom', dest='zoom', type = 'int', help='(auto mode only) Zoom. 0 value is maximum zoom')
    parser.add_option('--binary_filter', dest='filter', type = 'choice', choices = filters.keys())
    parser.add_option('--min_area', dest='min_area', type = 'int', help='min area of detected object in pixel at maximum zoom')
    parser.add_option('--max_area', dest='max_area', type = 'int', help='max area of detected object in pixel at maximum zoom')
    parser.add_option('--window_size', dest='window_size', type = 'int', help='window_size (sliding window). default is 1024')
    parser.add_option('--overlap', dest='overlap', type = 'int', help='overlap between two sliding window position in pixels. default is 0')
    options, arguments = parser.parse_args( args = argv)


    mode = options.mode if options.mode else modes.MANUAL

    #copy options
    id_image = options.id_image
    cytomine_host = options.cytomine_host if options.cytomine_host else 'ulb.cytomine.be'
    cytomine_public_key = options.cytomine_public_key if options.cytomine_public_key else '4b4ef932-204c-4fa4-b456-a50729f3519e'
    cytomine_private_key = options.cytomine_private_key if options.cytomine_private_key else 'afd8407e-5059-466a-bc8d-fe18dec63a4c'
    cytomine_base_path = options.cytomine_base_path if options.cytomine_base_path else "/api/"
    cytomine_working_path = options.cytomine_working_path if options.cytomine_working_path else "/tmp"
    zoom = options.zoom if options.zoom else int(0)
    overlap = options.overlap if options.overlap else int(0)    
    window_size = options.window_size if options.window_size else 1024
    min_area = options.min_area if options.min_area else (50*50 / (2**zoom)) #25x25 pixels at zoom 0
    max_area = options.min_area if options.min_area else (100000*100000 / (2**zoom)) #100000x100000 pixels at zoom 0
    filter = filters.get(options.filter)
    # init connection
    conn = Cytomine(cytomine_host, cytomine_public_key, cytomine_private_key, cytomine_working_path, base_path = cytomine_base_path, verbose = False)
    whole_slide = WholeSlide(conn.get_image_instance(id_image, True))

    async = False #True is experimental

    if mode == modes.AUTO:
        reader = CytomineReader(conn, whole_slide, window_position = Bounds(0,0, window_size, window_size), zoom = zoom, overlap = overlap)
        cv_image = cv.CreateImageHeader((reader.window_position.width, reader.window_position.height), cv.IPL_DEPTH_8U, 3)

        #sliding window test:
        reader.window_position = Bounds(0, 0, reader.window_position.width, reader.window_position.height)

        i = 0        

        geometries = []
        while True:
            reader.read(async = async)
            image=reader.data
            #Saving tile locally
            tile_filename = "%s/image-%d-tile-%d.png" %(cytomine_working_path,id_image,i)
            image.save(tile_filename,"PNG")
            cv.SetData(cv_image, reader.result().tostring())
            filtered_cv_image = filter.process(cv_image)
            i += 1
            components = ObjectFinder(filtered_cv_image).find_components()
            components = whole_slide.convert_to_real_coordinates(whole_slide, components, reader.window_position, reader.zoom)
            geometries.extend(Utils().get_geometries(components, min_area, max_area))
            
            if not reader.next(): break
        
        if options.publish_annotations:  
            conn.add_annotations(geometries, id_image)

        #save coordinates of detected geometries to local file
        #output = open(os.path.join(cytomine_working_path,save_to), 'wb')
        #pickle.dump(geometries, output, protocol=pickle.HIGHEST_PROTOCOL)
        #output.close()

if __name__ == '__main__':
    main(sys.argv[1:])
