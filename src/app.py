import json
import os
import datetime
import math
import io
from pprint import pprint # debug only

import bottle

# this is a customized version (PARSE_DECLTYPES and streaming responses)
import bottle_sqlite
import aggregate as agg
import gpximport

APP_ROOT = "."

app = bottle.Bottle()
app.install(bottle_sqlite.Plugin(dbfile=os.path.join(APP_ROOT, "data", "tracks.sqlite")))

#TODO: this is ugly and slow, JSON processing should be refactored (and use streaming)
class DateJSONEncoder(json.JSONEncoder):
  def default(self, o):
    # add tzinfo as it is stored without it
    if type(o) is datetime.datetime:
      return datetime.datetime(o.year, o.month, o.day, o.hour, o.minute, o.second, o.microsecond, datetime.timezone.utc).isoformat()
    else: json.JSONEncoder.default(self, o)

@app.route('/')
def index():
  return static("index.html")

@app.route("/static/<path:path>")
def static(path):
  return bottle.static_file(path, root=os.path.join(APP_ROOT, "static"))

@app.route("/tags")
def tag_list(db):
  bottle.response.set_header("Content-Type", "application/json")
  return DateJSONEncoder().iterencode(list(map(dict, db.execute("""
    SELECT tag_name,
      COUNT(*) AS track_count,
      MIN(lat_min) AS lat_min,
      MAX(lat_max) AS lat_max,
      MIN(lon_min) AS lon_min,
      MAX(lon_max) AS lon_max
    FROM tag
    JOIN track USING (track_id)
    GROUP BY tag_name"""))))

@app.route("/tags/<tag_name>")
def tracks_by_tag(tag_name, db):
  bottle.response.set_header("Content-Type", "application/json")
  #FIXME: WTF?????? this is done for post data but not for uris ??? WTF????
  tag_name = tag_name.encode("iso8859-1").decode("utf-8")
  tracks = db.execute("""
    SELECT track.*
    FROM tag
    JOIN track USING (track_id)
    WHERE tag_name=?""", (tag_name, )).fetchall()
  if len(tracks) == 0: bottle.abort(404, "No such tag.")
  return DateJSONEncoder().iterencode(list(map(dict, tracks)))

@app.route("/tracks")
def track_list(db):
  bottle.response.set_header("Content-Type", "application/json")
  return DateJSONEncoder().iterencode(list(map(dict, db.execute("SELECT * FROM track"))))

@app.route("/tracks", method="POST")
def add_track(db):
  name = bottle.request.forms.name
  tags = bottle.request.forms.tags.split()
  gpx = bottle.request.files.gpxfile

  if not (name and tags and gpx):
    bottle.abort(400, "Incomplete request: some fileds missing.")

  gpximport.process_gpx_file(io.TextIOWrapper(gpx.file, "utf-8"), name, tags, db)
  db.commit()
  bottle.response.status = 303
  bottle.response.set_header('Location', '/') 

@app.route("/tracks/<track_id:int>")
def track_detail(track_id, db):
  bottle.response.set_header("Content-Type", "application/json")
  t = db.execute("SELECT * FROM track WHERE track_id=?", (track_id, )).fetchone()
  if t is None: bottle.abort(404, "No such track.")
  return DateJSONEncoder().iterencode(dict(t))

@app.route("/tracks/<track_id:int>/points")
def track_points(track_id, db):
  bottle.response.set_header("Content-Type", "application/json")
  # As json does not support trailing comma (thanks IE team btw...) we need to know how many
  # points we are going to enumerate
  #TODO: make a look-ahead iterator to detect it without an extra request
  pt_count = db.execute("SELECT count(*) FROM point WHERE track_id=?", (track_id, )).fetchone()
  if pt_count is None: bottle.abort(404, "No such track.")
  
  pt_count = pt_count[0]
  points = db.execute("""
    SELECT timestamp, lat, lon, ele, distance_from_prev, speed 
    FROM point 
    WHERE track_id=? 
    ORDER BY seq""", (track_id, ))
  encoder = DateJSONEncoder()
  yield "["
  for p in points:
    yield encoder.encode(dict(p))
    pt_count -= 1
    if (pt_count > 0):  yield ","
  yield "]"

# track downsampling
# each method must work on it own range of values and has its own groupping column
# SQL group by operator is impossible to use here because groups may be missing and
# thus making less points than asked
downsample_range = {
  "seq": ("SELECT count(*) FROM point WHERE track_id=?", "seq"),
  "time": ("SELECT (julianday(end_date) - julianday(start_date)) * 86400 FROM track WHERE track_id=?", "time_from_start"),
  "distance": ("SELECT distance FROM track WHERE track_id=?", "distance_from_start")
}

@app.route("/tracks/<track_id:int>/downsampled")
def track_downsample(track_id, db):
  method = bottle.request.query.get("method", None, type=downsample_range.get)
  pt_count = bottle.request.query.get("points", None, type=int)
  if method is None: raise bottle.HTTPError(400, "Incorrect sampling method.")
  if pt_count is None or pt_count <= 1: raise bottle.HTTPError(400, "Incorrect point count.")

  total_range = db.execute(method[0], (track_id, )).fetchone()
  if total_range is None: bottle.abort(404, "No such track.")
  
  total_range = total_range[0] / (pt_count - 1)
  points = db.execute("""
    SELECT timestamp, lat, lon, ele, speed, %s AS grouping
    FROM point 
    WHERE track_id=? 
    ORDER BY seq""" % method[1], (track_id, ))
  last_point = points.fetchone()
  current_group = 1
  
  bottle.response.set_header("Content-Type", "application/json")
  encoder = DateJSONEncoder()
  accumulator = agg.Composite(lat=agg.Middle(), lon=agg.Middle(), ele=agg.Middle(), speed=agg.Avg(), timestamp=agg.Middle(datetime.datetime.max, datetime.datetime.min))
  yield "["
  yield encoder.encode(dict(last_point)) # the first point is always returned
  accumulator.step(last_point)
  for p in points:
    group = math.ceil(p["grouping"] / total_range)
    if group == current_group:
      # still on current group, accumulate row
      accumulator.step(p)
    elif group > current_group:
      # there were a (possibly multiple) group boundary, interpolate any missing point
      # it is a linear interpolation from between points not group, I think this is the most
      # simple and precise way to do
      missing = group - current_group
      for i in range(missing - 1):
        pt_count -= 1
        if (pt_count > 0):  yield ","
        yield encoder.encode({
          "lat": last_point["lat"] + ((p["lat"] - last_point["lat"]) / (missing + 1)),
          "lon": last_point["lon"] + ((p["lon"] - last_point["lon"]) / (missing + 1)),
          "ele": last_point["ele"] + ((p["ele"] - last_point["ele"]) / (missing + 1)),
          "speed": last_point["speed"] + ((p["speed"] - last_point["speed"]) / (missing + 1)),
          "timestamp": last_point["timestamp"] + ((p["timestamp"] - last_point["timestamp"]) / (missing + 1)),
        })
      pt_count -= 1
      if (pt_count > 0):  yield ","
      yield encoder.encode(accumulator.finalize())
      # start new group
      current_group = group
      accumulator = agg.Composite(lat=agg.Middle(), lon=agg.Middle(), ele=agg.Middle(), speed=agg.Avg(), timestamp=agg.Middle(datetime.datetime.max, datetime.datetime.min))
      accumulator.step(p)
    else: bottle.abort(500, "Incorrect data set")
    last_point = p
  yield "]"

app.run(host='0.0.0.0', port=8080, debug=True, reloader=True)
