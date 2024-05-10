drop table if exists card;
drop table if exists decks;
drop table if exists users;
drop table if exists user_ratings;

create table users (
  id integer primary key autoincrement,
  username text not null unique,
  password text not null,
  theme int default 0
);

create table decks (
  id integer primary key autoincrement,
  name text not null,
  description text not null,
  user_id integer not null,
  pub_or integer not null default 0,
  rating integer not null default 0,
  source integer default null,
  foreign key (user_id) references users(id)
);

create table card (
  id integer primary key autoincrement,
  title text not null,
  definition text not null,
  example text,
  deck_id integer not null,
  foreign key (deck_id) references decks(id)
);

create table user_ratings (
    id integer primary key autoincrement,
    user_id integer not null,
    deck_id integer not null,
    rating integer not null,
    unique(user_id, deck_id)
)

