set default_storage_engine=InnoDB;

drop database if exists atu_stack_prod;
create database atu_stack_prod character set utf8mb4 collate utf8mb4_unicode_ci;		-- 4byte UTF8 character set. 
																						-- Collation determines how strings are compared and sorted.
																						-- Unicode standard for sorting and comparisons here
																						-- ci for case insensitive
                                                                                        
use atu_stack_prod;

create table players (
    player_id int primary key auto_increment,
    firstname varchar(50) not null,
    lastname varchar(50) not null,
    username varchar(50) unique not null,
    password_hash varchar(255) not null,
    created_at timestamp default current_timestamp
);

create table resources (
    resource_id int primary key auto_increment,
    name varchar(30) not null unique
);

insert into resources (name) values
	('instant_noodles'),
	('caffeine'),
	('study'),
	('project_work');

create table player_resources (
    player_resource_id int primary key auto_increment,
    player_id int,
    resource_id int,
    quantity int default 0,
    unique (player_id, resource_id),
    foreign key (player_id) references players(player_id),
    foreign key (resource_id) references resources(resource_id)
);

create table structures (
    structure_id int primary key auto_increment,
    name varchar(50) not null unique,
    cost_instant_noodles int default 0,
    cost_caffeine int default 0,
    cost_study int default 0,
    cost_project_work int default 0
);

insert into structures (name, cost_instant_noodles, cost_caffeine, cost_study, cost_project_work) values
	('laptop', 2, 2, 1, 0),
	('pass_module', 3, 1, 3, 2),
	('honours_module', 4, 3, 4, 4),
	('shared_accommodation', 2, 3, 1, 1),
	('graduation_hat', 5, 5, 5, 5);

create table player_structures (
    player_structure_id int primary key auto_increment,
    player_id int,
    structure_id int,
    created_at timestamp default current_timestamp,
    foreign key (player_id) references players(player_id),
    foreign key (structure_id) references structures(structure_id)
);