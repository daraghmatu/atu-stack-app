SET default_storage_engine=InnoDB;

DROP DATABASE IF EXISTS atu_stack_prod;
CREATE DATABASE atu_stack_prod CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;		-- 4byte UTF8 character set. 
																						-- Collation determines how strings are compared and sorted.
																						-- Unicode standard for sorting and comparisons here
																						-- ci for case insensitive
                                                                                        
USE atu_stack_prod;


CREATE TABLE players (
    player_id INT PRIMARY KEY AUTO_INCREMENT,
    firstname VARCHAR(50) NOT NULL,
    lastname VARCHAR(50) NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    credits INT DEFAULT 0,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE TABLE resources (
    resource_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(20) UNIQUE NOT NULL
);

insert into resources (name) values
    ('pizza'),
    ('coffee'),
    ('sleep'),
    ('study');

CREATE TABLE player_resources (
    player_id INT,
    resource_id INT,
    quantity INT DEFAULT 0,
    PRIMARY KEY (player_id, resource_id),
    FOREIGN KEY (player_id) REFERENCES players(player_id) ON DELETE CASCADE,
    FOREIGN KEY (resource_id) REFERENCES resources(resource_id) ON DELETE CASCADE
);

CREATE TABLE tasks (
    task_id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(50) UNIQUE NOT NULL,
    pizza_cost INT NOT NULL,
    coffee_cost INT NOT NULL,
    sleep_cost INT NOT NULL,
    study_cost INT NOT NULL,
    credit_reward INT NOT NULL
);

insert into tasks (name, pizza_cost, coffee_cost, sleep_cost, study_cost, credit_reward) values
    ('CA Quiz', 0, 0, 1, 1, 1),
    ('Submit Assignment', 1, 1, 0, 2, 2),
    ('Exam', 2, 2, 2, 2, 5);

CREATE TABLE admin_settings (
    id INT PRIMARY KEY AUTO_INCREMENT,
    game_paused BOOLEAN DEFAULT FALSE,
    collection_paused BOOLEAN DEFAULT FALSE,
    tasks_paused BOOLEAN DEFAULT FALSE,
    trading_paused BOOLEAN DEFAULT FALSE,
    leaderboard_paused BOOLEAN DEFAULT FALSE
);

INSERT INTO admin_settings () VALUES ();  -- insert a row with defaults

CREATE TABLE player_history (
    history_id INT AUTO_INCREMENT PRIMARY KEY,
    player_id INT NOT NULL,
    action_type ENUM('collect', 'task', 'trade', 'hangover') NOT NULL,
    description TEXT,
    credits_earned INT DEFAULT 0,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE TABLE collect_log (
    player_id INT,
    collect_num INT,
    timestamp DATETIME
);

CREATE TABLE trades (
    trade_id INT AUTO_INCREMENT PRIMARY KEY,
    initiator_id INT NOT NULL,
    recipient_id INT NOT NULL,
    offered_resource_id INT NOT NULL,
    offered_quantity INT NOT NULL,
    requested_resource_id INT NOT NULL,
    requested_quantity INT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('pending', 'completed', 'cancelled') DEFAULT 'pending',
    FOREIGN KEY (initiator_id) REFERENCES players(player_id),
    FOREIGN KEY (recipient_id) REFERENCES players(player_id),
    FOREIGN KEY (offered_resource_id) REFERENCES resources(resource_id),
    FOREIGN KEY (requested_resource_id) REFERENCES resources(resource_id)
);

-- Trigger to assign starting resources
DELIMITER //

CREATE TRIGGER assign_starting_resources
AFTER INSERT ON players
FOR EACH ROW
BEGIN
    INSERT INTO player_resources (player_id, resource_id, quantity)
    VALUES
        (NEW.player_id, (SELECT resource_id FROM resources WHERE name = 'Pizza'), FLOOR(RAND() * 6)),
        (NEW.player_id, (SELECT resource_id FROM resources WHERE name = 'Coffee'), FLOOR(RAND() * 6)),
        (NEW.player_id, (SELECT resource_id FROM resources WHERE name = 'Sleep'), FLOOR(RAND() * 6)),
        (NEW.player_id, (SELECT resource_id FROM resources WHERE name = 'Study'), FLOOR(RAND() * 6));
END;
//

DELIMITER ;