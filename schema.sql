drop table if exists session;
drop table if exists telemetry_data;

create table session (
    id integer primary key autoincrement,
    datetime text unique not null
);

create table telemetry_data (
    id integer primary key autoincrement,
    session text,
    time float,
    alt float,
    temp float,
    acc_x float,
    acc_y float,
    acc_z float,
    acc_mag float,
    foreign key (session) references session(id)
);
