create table track(
  track_id integer primary key,
  name text not null,
  description text,
  start_date timestamp,
  end_date timestamp,
  distance real,   -- in m
  max_speed real,  -- in m/s
  uphill real,
  downhill real,
  -- bounds
  lat_min real,
  lat_max real,
  lon_min real,
  lon_max real,
  ele_min real,
  ele_max real
);

create table point(
  track_id integer not null references track(track_id),
  seq integer not null,
  timestamp timestamp not null,
  lat real not null,
  lon real not null,
  ele real not null,
  speed real not null,
  distance_from_prev real not null,
  distance_from_start real not null,
  time_from_start real not null,
  constraint pk_points primary key (track_id, seq)
);

-- indexes used for downsampling
--create index ids_point_dist on point (track_id, )
