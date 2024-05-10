drop table if exists telemetry_data;

create table telemetry_data (
    id integer primary key autoincrement,
    altitude number,
    temperature number,
    acceleration_x number,
    acceleration_y number,
    acceleration_z number,
    acceleration_mag number
);
