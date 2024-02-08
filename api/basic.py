'''
- CSV is not saved on the server 
- uses BytesIO class to create a file-like object in memory
- passes  pandas dataframe via JSON to onother view using session
- implemented limit to CSV files -- this needs a handler 413 error
- displays Table with data 
- displays point on the leaflet map
- can export data in shapefile and geojson formats 
- checks if the right column names were given: X and y or lat and lon latitude and longitude  


WORKING ON:
    - the file passed via session meets the default requirement 
    - this is handled in the code 


Keep in mind that while the default Flask session is convenient for small amounts of data, it may 
not be suitable for storing large datasets due to cookie size limitations. For larger datasets, you might 
consider other storage options, such as server-side sessions or database-backed sessions.

Flask provides the flexibility to implement session storage in various ways beyond the default client-side storage. 
Here are two common alternatives:
    -   Server-side Sessions
    -   Database-backed Sessions

'''


from flask import (Flask, render_template, redirect, 
                   url_for,request, session, flash, send_file, jsonify)
import pandas as pd
import geopandas
import simplekml
from pandas.api.types import is_numeric_dtype
import os
import io
import tempfile
import zipfile

app = Flask(__name__)

app.config['SECRET_KEY'] = 'mysecretkey'
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1 megabytes

# Define allowed files
ALLOWED_EXTENSIONS = {'csv'}

def validate_columns_df(df):

    columns = list(df.columns)
    columns = [c.lower().strip() for c in columns]
    # CSV will only be accepted if the table contains X and Y columns or latitude and longitude or lat and lon. and only if the columns contain numeric data.
    print(columns)
    if 'x' in columns and 'y' in columns:
        for e in list(df.columns):
            if e.lower().strip() == 'x':
                print('YEYYYYYYYYYYY', is_numeric_dtype(df[e]))
                session['x'] = e
                continue
            if e.lower().strip() == 'y':
                session['y'] = e
                continue
        if is_numeric_dtype(df[session['x']]) and is_numeric_dtype(df[session['y']]):
            return True
    
    if 'latitude' in columns and 'longitude' in columns:
        for e in df.columns:
            if e.lower().strip() == 'latitude':
                session['y'] = e
                continue
            if e.lower().strip() == 'longitude':
                session['x'] = e
                continue
        if is_numeric_dtype(df[session['x']]) and is_numeric_dtype(df[session['y']]):
            return True
    
    if 'lat' in columns and 'lon' in columns:
        for e in df.columns:
            if e.lower().strip() == 'lat':
                session['y'] = e
                continue
            if e.lower().strip() == 'lon':
                session['x'] = e
                continue
        if is_numeric_dtype(df[session['x']]) and is_numeric_dtype(df[session['y']]):
            return True
    
    return False


def get_data_size(data):
    # Serialize data to JSON and measure its length
    data_json = jsonify(data).get_data(as_text=True)
    return len(data_json)


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/upload-data',methods=['GET', 'POST'])
def upload_data():

    if request.method == 'POST':
        # Check if the post request has the file part
        # if not then redirects user to http://127.0.0.1:5000/upload-data
        if 'file' not in request.files:
            flash('Something has gone wrong. The file was not uploaded. Please try again.')
            return redirect(request.url)
        
        file = request.files['file']

        # If the user does not select a file, the browser submits an empty file without a filename
        if file.filename == '':
            flash('File not provided.')
            return redirect(request.url)
        
        if file and file.filename[len(file.filename) - 4:] != '.csv':
            flash('Only CSV files are allowed.')
            return redirect(request.url)
        
        if file and file.filename[len(file.filename) - 4:] == '.csv':
            # using the BytesIO class to create a file-like object in memory
            csv_data = io.StringIO(file.stream.read().decode("UTF8"), newline="")

            df = pd.read_csv(csv_data)

            # # validate columns if the table contains X and Y or latitude and longitude or lat and long
            if not validate_columns_df(df):
                flash('CSV will only be accepted if the table contains X and Y columns or latitude and longitude or lat and lon. and only if the columns contain numeric data.')
                return redirect(request.url)

            # needs to convert dataframe to JSON to be able to pass data via SESSION 
            df_json = df.to_json()

            # Check if data size exceeds the limit (adjust as needed)
            data_size_limit = 4096  # his is default session maximum

            if get_data_size(df_json) > data_size_limit:
                flash('Data is too large. Please reduce the data size')
                return redirect(request.url)
    
            session['df_data'] = df_json
            
            return redirect(url_for('data_menu'))

    return render_template('uploader.html')


def convert_to_coordinates(data):
    '''
    - converts X and Y coordinates into the 2D list
    - and returns as a dictionary
    '''
    Y = list(data[session['y']])
    X = list(data[session['x']])
    coordinates = list(zip(Y, X))
    coordinates = {"coordinates": coordinates}

    return coordinates



@app.route('/data-menu',methods=['GET', 'POST'])
def data_menu():
    # Retrieving JSON string from session and converting it back to DataFrame
    df_json = session.get('df_data', None)

    # trigered when 'DOWNLOAD BUTTON SELECTED'
    if request.method == 'POST' and df_json:
        selected_format = request.form.get('dropdown') 

        df = pd.read_json(df_json)

        # converting dataframe to geodataframe
        points = geopandas.GeoDataFrame(
            df, geometry=geopandas.points_from_xy(df[session['x']], df[session['y']])).set_crs("EPSG:4326")

        
        # converting geodataframe to geojson
        if selected_format == 'geojson':
            # # Create a temporary GeoJSON file
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, 'output.geojson')
            point_geojeson = points.to_file(temp_file_path, driver='GeoJSON')
            return send_file(temp_file_path, download_name='output.geojson', as_attachment=True)

        # converting geodataframe to shapefile
        if selected_format == 'shapefile':
            temp_file = io.BytesIO()
           # Create a temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Write GeoDataFrame to a temporary shapefile
                temp_shapefile_path = os.path.join(temp_dir, 'output_shapefile.shp')
                points.to_file(temp_shapefile_path, driver='ESRI Shapefile')

                # Create a Zip file
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
                    # Add shapefile components to the Zip file
                    zip_file.write(temp_shapefile_path, 'output_shapefile.shp')
                    zip_file.write(temp_shapefile_path.replace('.shp', '.shx'), 'output_shapefile.shx')
                    zip_file.write(temp_shapefile_path.replace('.shp', '.prj'), 'output_shapefile.prj')

            # Move the buffer cursor to the beginning of the buffer
            zip_buffer.seek(0)
            # Return the zipped shapefile as a response
            return send_file(zip_buffer, download_name='output_shapefile.zip', as_attachment=True, mimetype='application/zip')

        # converting geodataframe to KML
        if selected_format == 'kml':
            # Create an in-memory buffer
            buffer = io.BytesIO()

            kml = simplekml.Kml()
            df_dic = df.to_dict(orient='index')
            for k in df_dic:
                print(k, df_dic[k])
                data = df_dic[k]
                placemark = kml.newpoint(name=str(k), coords=[(data[session['x']], data[session['y']])]) # [long & lat] [x,y]
                for e in data:
                    placemark.extendeddata.newdata(str(e), str(data[e]))

            # Write KML to the buffer
            buffer.write(kml.kml().encode())

            # Move the buffer cursor to the beginning of the buffer
            buffer.seek(0)

            # Return the KML file as a response
            return send_file(buffer, download_name='output.kml', as_attachment=True, mimetype='application/vnd.google-earth.kml+xml')

    # trigered when data uploaded in the uploader 
    if df_json:
        df = pd.read_json(df_json)
        coordinates = convert_to_coordinates(df)
        
        print(coordinates)

        return render_template('data_menu.html', df=df.to_html(classes="table table-bordered table-striped table table-hover"), coordinates=coordinates)
    
    
    return render_template('data_menu.html', df=None)

@app.errorhandler(413)
def request_entity_too_large(error):
    return render_template('413_error.html'), 413


if __name__ == '__main__':
    app.run()