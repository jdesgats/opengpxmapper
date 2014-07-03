#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
#sys.path.insert(0, os.getcwd())

import lib.gpxpy as gpxpy
import sqlite3
import datetime

def utc(d):
  """ As default datetime converter for datetime is not able to handle timezont, let's remove it..."""
  d = d if d.tzinfo is None else d.astimezone(datetime.timezone.utc)
  return datetime.datetime(d.year, d.month, d.day, d.hour, d.minute, d.second, d.microsecond)

def sanitize(points):
  """ Sometimes points are not ordered chonologically ! """
  out = [ points[0] ]
  for p in points[1:]:
    if p.time >= out[-1].time:
      out.append(p)
    else:
      print("Drop point %s because it is not chronologically ordered." % p)
  return out

def process_track(track, name, tags, db):
  # merge segments as we don't support them
  while len(track.segments) > 1: track.join(0, 1)
  seg = track.segments[0]
  seg.smooth(True, True, True)
  t, b, ele, hill = seg.get_time_bounds(), seg.get_bounds(), seg.get_elevation_extremes(), seg.get_uphill_downhill()
  c = db.cursor()
  c.execute("""
    INSERT INTO track (
      name, 
      start_date, end_date, 
      distance, max_speed, 
      uphill, downhill,
      lat_min, lat_max, 
      lon_min, lon_max, 
      ele_min, ele_max)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
    (
      name or track.name,
      utc(t.start_time), utc(t.end_time),
      track.length_3d(), track.get_moving_data().max_speed,
      hill.uphill, hill.downhill,
      b.min_latitude, b.max_latitude,
      b.min_longitude, b.max_longitude,
      ele.minimum, ele.maximum,
    ))
  track_id = c.lastrowid
  start_time = seg.points[0].time
  dist_acc = [0, ] # nonlocal keyword is a non working wtf...
  points = sanitize(seg.points)
  
  def point_data(pt, i):
    dfp = 0 if i==0 else pt.distance_3d(seg.points[i-1])
    dist_acc[0] += dfp
    return (track_id, i, utc(pt.time), pt.latitude, pt.longitude, pt.elevation, seg.get_speed(i) or 0, dfp, dist_acc[0], (pt.time - start_time).total_seconds())
  db.executemany(
    "INSERT INTO point (track_id, seq, timestamp, lat, lon, ele, speed, distance_from_prev, distance_from_start, time_from_start) VALUES (?,?,?,?,?,?,?,?,?,?)",
    map(point_data, points, range(len(points))))
  db.executemany("INSERT INTO tag (tag_name, track_id) VALUES (?,?)", (( t, track_id ) for t in tags))

def process_gpx_file(gpx_file, name, tags, db):
  gpx = gpxpy.parse(gpx_file)
  for track in gpx.tracks:
    process_track(track, name, tags, db)

if __name__ == "__main__":
  db = sqlite3.connect("data/tracks.sqlite", detect_types=sqlite3.PARSE_DECLTYPES)
  process_gpx_file(sys.stdin, None, [], db)
  db.commit()
