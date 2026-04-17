PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE schema_version (
    version       INTEGER PRIMARY KEY,
    applied_at    TEXT    NOT NULL,
    description   TEXT    NOT NULL
) STRICT;
INSERT INTO schema_version VALUES(1,'2026-04-11','Phase 0 initial schema');
CREATE TABLE body_metrics (
    date            TEXT    PRIMARY KEY,              -- YYYY-MM-DD
    weight_lbs      REAL,
    weight_kg       REAL,
    body_fat_pct    REAL,                              -- Renpho bioimpedance, NOT DEXA truth
    muscle_mass_kg  REAL,                              -- nullable: Fitbit doesn't always return
    water_pct       REAL,                              -- nullable
    bmi             REAL,
    source          TEXT    NOT NULL,                  -- FITBIT | TELEGRAM | RENPHO | MANUAL
    notes           TEXT
) STRICT;
INSERT INTO body_metrics VALUES('2026-03-08',184.099999999999994,83.5,NULL,NULL,NULL,28.2600000000000015,'FITBIT','synced 19:39 ET');
INSERT INTO body_metrics VALUES('2026-03-09',183.599999999999994,83.2999999999999971,NULL,NULL,NULL,28.1700000000000017,'FITBIT','synced 19:39 ET');
INSERT INTO body_metrics VALUES('2026-03-10',183.400000000000005,83.2000000000000028,NULL,NULL,NULL,28.1400000000000005,'FITBIT','synced 19:39 ET');
INSERT INTO body_metrics VALUES('2026-03-11',182.300000000000011,82.7000000000000028,NULL,NULL,NULL,27.9800000000000004,'FITBIT','synced 19:39 ET');
INSERT INTO body_metrics VALUES('2026-03-12',181.0,82.0999999999999943,NULL,NULL,NULL,27.7699999999999995,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-13',180.099999999999994,81.7000000000000028,NULL,NULL,NULL,27.629999999999999,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-14',179.0,81.2000000000000028,NULL,NULL,NULL,27.4600000000000008,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-15',178.800000000000011,81.0999999999999943,NULL,NULL,NULL,27.4299999999999997,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-16',179.900000000000005,81.5999999999999943,22.8000000000000007,NULL,NULL,27.5799999999999982,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-17',176.800000000000011,80.2000000000000028,22.1000000000000014,NULL,NULL,27.129999999999999,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-18',176.800000000000011,80.2000000000000028,22.1000000000000014,NULL,NULL,27.1099999999999994,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-19',177.300000000000011,80.4000000000000056,22.1999999999999992,NULL,NULL,27.1799999999999997,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-20',176.099999999999994,79.9000000000000056,22.0,NULL,NULL,27.0199999999999995,'FITBIT','synced 19:40 ET');
INSERT INTO body_metrics VALUES('2026-03-25',179.900000000000005,81.5999999999999943,22.8000000000000007,NULL,NULL,27.5799999999999982,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-03-27',177.900000000000005,80.7000000000000028,22.3000000000000007,NULL,NULL,27.2800000000000011,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-03-28',178.599999999999994,81.0,22.5,NULL,NULL,27.3999999999999985,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-03-29',177.300000000000011,80.4000000000000056,22.1999999999999992,NULL,NULL,27.1900000000000012,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-03-30',176.400000000000005,80.0,22.0,NULL,NULL,27.0399999999999991,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-03-31',175.699999999999988,79.7000000000000028,21.8000000000000007,NULL,NULL,26.9600000000000008,'FITBIT','synced 19:41 ET');
INSERT INTO body_metrics VALUES('2026-04-01',174.199999999999988,79.0,21.5,NULL,NULL,26.6999999999999992,'FITBIT','synced 19:42 ET');
INSERT INTO body_metrics VALUES('2026-04-02',174.800000000000011,79.2999999999999971,21.6000000000000014,NULL,NULL,26.8200000000000002,'FITBIT','synced 19:42 ET');
INSERT INTO body_metrics VALUES('2026-04-03',177.699999999999988,80.5999999999999943,22.3000000000000007,NULL,NULL,27.2600000000000015,'FITBIT','synced 19:42 ET');
INSERT INTO body_metrics VALUES('2026-04-04',177.699999999999988,80.5999999999999943,22.3000000000000007,NULL,NULL,27.2600000000000015,'FITBIT',NULL);
INSERT INTO body_metrics VALUES('2026-04-05',175.300000000000011,79.5,21.8000000000000007,NULL,NULL,26.8900000000000005,'FITBIT','synced 20:13 ET');
INSERT INTO body_metrics VALUES('2026-04-06',174.199999999999988,79.0,21.5,NULL,NULL,26.7199999999999988,'FITBIT','synced 22:33 ET');
INSERT INTO body_metrics VALUES('2026-04-07',173.300000000000011,78.5999999999999943,21.3000000000000007,NULL,NULL,26.7199999999999988,'FITBIT','synced 10:16 ET');
INSERT INTO body_metrics VALUES('2026-04-08',173.099999999999994,78.5,21.1999999999999992,NULL,NULL,26.6900000000000012,'FITBIT','synced 10:16 ET');
INSERT INTO body_metrics VALUES('2026-04-09',172.800000000000011,78.4000000000000056,21.1999999999999992,NULL,NULL,26.6499999999999985,'FITBIT','synced 10:16 ET');
INSERT INTO body_metrics VALUES('2026-04-10',172.0,78.0,21.0,NULL,NULL,26.5199999999999995,'FITBIT','synced 10:16 ET');
INSERT INTO body_metrics VALUES('2026-04-11',172.0,78.0,21.0,NULL,NULL,26.5199999999999995,'FITBIT','synced 10:16 ET');
INSERT INTO body_metrics VALUES('2026-04-12',173.699999999999988,78.7999999999999971,21.3999999999999985,NULL,NULL,26.7899999999999991,'FITBIT','synced 09:11 ET');
INSERT INTO body_metrics VALUES('2026-04-13',175.900000000000005,79.7999999999999971,21.8999999999999985,NULL,NULL,27.1200000000000009,'FITBIT','synced 16:00 ET');
INSERT INTO body_metrics VALUES('2026-04-14',175.900000000000005,79.7999999999999971,22.0,NULL,NULL,27.1200000000000009,'FITBIT','synced 16:00 ET');
INSERT INTO body_metrics VALUES('2026-04-15',171.699999999999988,77.9000000000000056,21.0,NULL,NULL,26.4800000000000004,'FITBIT','synced 16:00 ET');
INSERT INTO body_metrics VALUES('2026-04-16',172.0,78.0,NULL,NULL,NULL,26.5199999999999995,'FITBIT','synced 11:00 ET');
INSERT INTO body_metrics VALUES('2026-04-17',173.099999999999994,78.5,21.3000000000000007,NULL,NULL,26.6900000000000012,'FITBIT','synced 11:00 ET');
CREATE TABLE body_scan (
    date                        TEXT    PRIMARY KEY,  -- YYYY-MM-DD
    scan_type                   TEXT    NOT NULL,     -- DEXA | InBody | other
    total_bf_pct                REAL,
    lean_mass_lbs               REAL,
    lean_mass_kg                REAL,
    bone_density                REAL,                  -- g/cm²
    visceral_fat_area           REAL,                  -- cm²
    trunk_fat_pct               REAL,
    arms_fat_pct                REAL,
    legs_fat_pct                REAL,
    renpho_bf_same_week         REAL,                  -- for DEXA-Renpho offset calibration
    dexa_renpho_offset          REAL,                  -- BF% delta for reconciling Renpho readings
    rmr_cal                     REAL,                  -- DEXA-derived RMR
    source                      TEXT    NOT NULL,      -- usually DEXA
    source_file                 TEXT,                  -- original PDF filename
    notes                       TEXT
) STRICT;
INSERT INTO body_scan VALUES('2026-04-02','DEXA',26.3000000000000007,128.599999999999994,58.2999999999999971,1.26400000000000001,71.0499999999999971,31.3000000000000007,20.6999999999999992,22.6000000000000014,NULL,NULL,1618.0,'DEXA PDF','fitness/uploads/dexa_2026-04-02.pdf','First baseline scan. A/G ratio 1.28, VAT 1.46 lbs, RSMI 10.13. Added RMR column and value — extracted from DEXA PDF 2026-04-02. RMR: 1618 cal/day');
CREATE TABLE nutrition (
    date         TEXT    PRIMARY KEY,
    calories     REAL,
    protein_g    REAL,
    carbs_g      REAL,
    fat_g        REAL,
    fiber_g      REAL,
    sodium_mg    REAL,
    source       TEXT    NOT NULL,                      -- FITBIT | TELEGRAM | MANUAL
    notes        TEXT
) STRICT;
INSERT INTO nutrition VALUES('2026-03-08',2085.0,95.0,256.0,89.0,39.0,4231.0,'FITBIT','synced 19:39 ET');
INSERT INTO nutrition VALUES('2026-03-09',1720.0,166.0,108.0,82.0,28.0,3971.0,'FITBIT','synced 19:39 ET');
INSERT INTO nutrition VALUES('2026-03-10',2964.0,372.0,166.0,104.0,33.0,4889.0,'FITBIT','synced 19:39 ET');
INSERT INTO nutrition VALUES('2026-03-11',4152.0,501.0,95.0,160.0,4.0,3580.0,'FITBIT','synced 19:39 ET');
INSERT INTO nutrition VALUES('2026-03-12',1951.0,203.0,116.0,91.0,25.0,2163.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-13',1771.0,171.0,116.0,84.0,17.0,1304.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-14',1274.0,194.0,59.0,29.0,3.0,1646.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-15',1438.0,158.0,116.0,57.0,46.0,2389.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-16',1448.0,139.0,39.0,84.0,8.0,1813.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-17',1448.0,186.0,73.0,51.0,13.0,2708.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-18',1454.0,146.0,145.0,60.0,55.0,4163.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-19',1661.0,180.0,71.0,87.0,39.0,2532.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-20',2949.0,220.0,227.0,154.0,74.0,3452.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-21',705.0,9.0,76.0,41.0,1.0,700.0,'FITBIT','synced 19:40 ET');
INSERT INTO nutrition VALUES('2026-03-22',370.0,0.0,67.0,12.0,0.0,323.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-23',370.0,0.0,67.0,12.0,0.0,323.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-24',520.0,56.0,32.0,20.0,2.0,300.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-25',2400.0,194.0,171.0,110.0,22.0,4620.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-26',1699.0,100.0,160.0,79.0,9.0,3311.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-27',1518.0,142.0,122.0,64.0,23.0,1408.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-28',1380.0,115.0,178.0,35.0,27.0,1968.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-29',2123.0,203.52000000000001,135.569999999999993,83.3299999999999982,13.4000000000000003,1856.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-30',4069.0,405.490000000000009,300.100000000000022,149.650000000000005,18.5,5978.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-03-31',1588.0,122.0,105.0,94.0,36.0,1135.0,'FITBIT','synced 19:41 ET');
INSERT INTO nutrition VALUES('2026-04-01',3998.0,382.0,247.0,174.0,44.0,3970.0,'FITBIT','synced 19:42 ET');
INSERT INTO nutrition VALUES('2026-04-02',1860.0,98.0,232.0,75.0,29.0,2255.0,'FITBIT','synced 19:42 ET');
INSERT INTO nutrition VALUES('2026-04-03',1280.0,115.0,99.0,60.0,27.0,2049.0,'FITBIT','synced 19:42 ET');
INSERT INTO nutrition VALUES('2026-04-04',1400.0,168.0,47.0,61.0,4.0,1656.0,'FITBIT',NULL);
INSERT INTO nutrition VALUES('2026-04-05',3146.0,186.0,328.0,122.0,26.0,6372.0,'FITBIT','synced 20:13 ET');
INSERT INTO nutrition VALUES('2026-04-06',1826.0,197.0,196.0,36.0,35.0,4410.0,'FITBIT','synced 22:34 ET');
INSERT INTO nutrition VALUES('2026-04-07',1402.0,172.0,120.0,33.0,24.0,1558.0,'FITBIT','synced 10:16 ET');
INSERT INTO nutrition VALUES('2026-04-08',2435.0,160.0,124.0,148.0,20.0,1821.0,'FITBIT','synced 10:16 ET');
INSERT INTO nutrition VALUES('2026-04-09',1623.0,105.0,181.0,53.0,8.0,1173.0,'FITBIT','synced 10:16 ET');
INSERT INTO nutrition VALUES('2026-04-10',3132.0,127.0,262.0,182.0,14.0,4000.0,'FITBIT','synced 10:16 ET');
INSERT INTO nutrition VALUES('2026-04-11',3399.0,119.0,350.0,169.0,23.0,3830.0,'FITBIT','synced 10:16 ET');
INSERT INTO nutrition VALUES('2026-04-12',3542.0,144.0,506.0,102.0,27.0,5260.0,'FITBIT','synced 09:11 ET');
INSERT INTO nutrition VALUES('2026-04-13',1813.0,140.0,184.0,76.0,54.0,7010.0,'FITBIT','synced 16:00 ET');
INSERT INTO nutrition VALUES('2026-04-14',1304.0,146.0,115.0,38.0,28.0,1912.0,'FITBIT','synced 16:00 ET');
INSERT INTO nutrition VALUES('2026-04-15',2037.0,110.0,189.0,98.0,16.0,1730.0,'FITBIT','synced 16:00 ET');
INSERT INTO nutrition VALUES('2026-04-16',1574.0,168.0,135.0,50.0,31.0,2243.0,'FITBIT','synced 11:00 ET');
INSERT INTO nutrition VALUES('2026-04-17',992.0,130.0,58.0,32.0,18.0,1115.0,'FITBIT','synced 11:00 ET');
CREATE TABLE workout (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT    NOT NULL,
    exercise      TEXT    NOT NULL,
    sets          INTEGER NOT NULL,
    reps          INTEGER NOT NULL,
    weight_lbs    REAL    NOT NULL,                    -- 0 OK for bodyweight
    rpe           REAL,                                  -- nullable; RPE 0–10
    volume_lbs    REAL,                                  -- stored (not computed) to match sheet
    session_type  TEXT,                                  -- BRO_SPLIT_LEGS, UPPER, etc.
    source        TEXT    NOT NULL,                      -- TELEGRAM | MANUAL
    notes         TEXT
) STRICT;
INSERT INTO workout VALUES(1,'2026-04-04','Leg Press',3,8,320.0,NULL,7680.0,'Legs & Abs','TELEGRAM',NULL);
INSERT INTO workout VALUES(2,'2026-04-04','Leg Extension',3,8,135.0,NULL,3240.0,'Legs & Abs','TELEGRAM',NULL);
INSERT INTO workout VALUES(3,'2026-04-04','Captain Chair',3,8,8.0,NULL,192.0,'Legs & Abs','TELEGRAM',NULL);
INSERT INTO workout VALUES(4,'2026-04-06','Pull Ups',1,7,174.199999999999988,NULL,1219.40000000000009,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(5,'2026-04-06','Lat Pull Downs',1,8,160.0,NULL,1280.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(6,'2026-04-06','Lat Pull Downs',1,5,160.0,NULL,800.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(7,'2026-04-06','Lat Pull Downs',1,8,160.0,NULL,1280.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(8,'2026-04-06','Reverse Pec Fly',1,10,115.0,NULL,1150.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(9,'2026-04-06','Reverse Pec Fly',1,7,115.0,NULL,805.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(10,'2026-04-06','Reverse Pec Fly',1,4,115.0,NULL,460.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(11,'2026-04-06','Preacher Dumbbell Curls Left',3,10,25.0,NULL,750.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(12,'2026-04-06','Preacher Dumbbell Curls Right',3,10,25.0,NULL,750.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(13,'2026-04-07','Incline Dumbbell Press',3,3,50.0,NULL,450.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(14,'2026-04-07','Single Arm Cable Lateral Raise',3,10,12.5,NULL,375.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(15,'2026-04-07','Seated Pec Fly Machine',3,8,130.0,NULL,3120.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(16,'2026-04-07','Shoulder Press Machine',3,6,80.0,NULL,1440.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(17,'2026-04-08','Leg Press',3,8,320.0,NULL,7680.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(18,'2026-04-08','Leg Curl',3,10,100.0,NULL,3000.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(19,'2026-04-08','Leg Extension',3,10,140.0,NULL,4200.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(20,'2026-04-08','Weighted Captain Chair',3,10,8.0,NULL,240.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(21,'2026-04-09','Pull Ups',7,1,172.800000000000011,NULL,1209.5999999999999,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(22,'2026-04-09','Lat Pulldown',3,8,160.0,NULL,3840.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(23,'2026-04-09','Seated Row Machine',3,10,85.0,NULL,2550.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(24,'2026-04-09','Reverse Pec Fly',3,8,100.0,NULL,2400.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(25,'2026-04-09','Preacher Dumbbell Curls Left',3,10,25.0,NULL,750.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(26,'2026-04-09','Preacher Dumbbell Curls Right',3,10,25.0,NULL,750.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(27,'2026-04-11','Seated Leg Press',3,10,320.0,NULL,9600.0,'BRO_SPLIT','TELEGRAM',NULL);
INSERT INTO workout VALUES(28,'2026-04-11','Weighted Captain Chair',3,10,10.0,NULL,300.0,'BRO_SPLIT','TELEGRAM',NULL);
CREATE TABLE cardio (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT    NOT NULL,
    exercise       TEXT    NOT NULL,                     -- Treadmill, Bike, etc.
    duration_min   REAL    NOT NULL,
    speed          REAL,                                 -- mph or km/h
    incline        REAL,                                 -- %
    net_calories   REAL,
    met_used       REAL,
    source         TEXT    NOT NULL,
    notes          TEXT
) STRICT;
INSERT INTO cardio VALUES(1,'2026-04-06','Treadmill',45.0,3.5,3.5,284.0,5.0,'TELEGRAM','45 min at 4.5 mph, 4.5% incline. Net 378 kcal using user''s measured RMR 1618. ACSM equation (VO2 25.35 ml/kg/min).');
INSERT INTO cardio VALUES(2,'2026-04-07','Treadmill',45.0,NULL,NULL,284.0,5.0,'TELEGRAM','3.5 mph at 3.5% incline. Net calories calculated from user''s RMR 1618 and ACSM treadmill equation.');
INSERT INTO cardio VALUES(3,'2026-04-09','Treadmill',45.0,3.5,3.5,245.0,4.79999999999999982,'TELEGRAM','Updated with calculated net calories burned based on current weight and RMR');
CREATE TABLE recovery (
    date                  TEXT    PRIMARY KEY,
    efficiency_pct        REAL,                          -- % of time in bed asleep (was misnamed "Sleep Score")
    sleep_hours           REAL,                          -- total actual asleep (all sessions, post-04-11 fix)
    steps                 INTEGER,
    active_minutes        INTEGER,
    hrv                   REAL,                          -- nullable: not in standard Fitbit Web API
    resting_hr            INTEGER,
    sleep_score_computed  REAL,                          -- 0-100 proxy formula (added 2026-04-11)
    time_in_bed_h         REAL,                          -- raw, includes wake within sessions (added 2026-04-11)
    source                TEXT    NOT NULL,
    notes                 TEXT
) STRICT;
INSERT INTO recovery VALUES('2026-03-05',90.0,5.70000000000000017,6331,72,NULL,61,83.0,6.29999999999999982,'FITBIT','deep:68m light:187m rem:86m wake:37m synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-06',NULL,NULL,3519,38,NULL,62,NULL,NULL,'FITBIT','synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-07',NULL,NULL,37187,359,NULL,62,NULL,NULL,'FITBIT','synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-08',NULL,NULL,15474,140,NULL,63,NULL,NULL,'FITBIT','synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-09',94.0,6.29999999999999982,13450,126,NULL,64,88.0,6.70000000000000017,'FITBIT','deep:78m light:185m rem:117m wake:22m synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-10',89.0,6.20000000000000017,13121,110,NULL,64,86.0,7.0,'FITBIT','deep:67m light:232m rem:73m wake:46m synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-11',93.0,6.20000000000000017,9371,38,NULL,64,87.0,6.70000000000000017,'FITBIT','deep:70m light:211m rem:94m wake:27m synced 19:39 ET');
INSERT INTO recovery VALUES('2026-03-12',NULL,NULL,13405,88,NULL,65,NULL,NULL,'FITBIT','synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-13',90.0,5.40000000000000035,11316,115,NULL,65,81.0,6.0,'FITBIT','deep:77m light:161m rem:88m wake:35m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-14',93.0,4.59999999999999964,16070,109,NULL,66,77.0,4.90000000000000035,'FITBIT','deep:73m light:122m rem:80m wake:20m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-15',96.0,6.5,10577,68,NULL,66,90.0,6.79999999999999982,'FITBIT','deep:76m light:213m rem:101m wake:18m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-16',98.0,4.40000000000000035,13459,101,NULL,64,77.0,4.5,'FITBIT','deep:82m light:122m rem:62m wake:6m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-17',89.0,4.70000000000000017,9618,61,NULL,63,77.0,5.20000000000000017,'FITBIT','deep:77m light:143m rem:59m wake:32m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-18',88.0,6.09999999999999964,13712,79,NULL,61,85.0,6.90000000000000035,'FITBIT','deep:72m light:196m rem:96m wake:48m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-19',91.0,7.20000000000000017,6693,35,NULL,61,93.0,7.90000000000000035,'FITBIT','deep:98m light:209m rem:127m wake:42m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-20',92.0,4.40000000000000035,18661,150,NULL,60,76.0,4.79999999999999982,'FITBIT','deep:46m light:167m rem:53m wake:23m synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-21',NULL,NULL,12900,116,NULL,60,NULL,NULL,'FITBIT','synced 19:40 ET');
INSERT INTO recovery VALUES('2026-03-22',91.0,8.0,1075,8,NULL,61,98.0,8.80000000000000071,'FITBIT','deep:112m light:259m rem:108m wake:50m synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-23',NULL,NULL,0,0,NULL,NULL,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-24',NULL,NULL,0,0,NULL,NULL,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-25',NULL,NULL,4639,67,NULL,NULL,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-26',NULL,NULL,0,0,NULL,NULL,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-27',NULL,NULL,0,0,NULL,NULL,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-28',NULL,NULL,4622,12,NULL,61,NULL,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-29',92.0,6.40000000000000035,21588,178,NULL,62,88.0,6.90000000000000035,'FITBIT','deep:56m light:226m rem:100m wake:33m synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-30',90.0,7.09999999999999964,23170,214,NULL,63,92.0,7.90000000000000035,'FITBIT','deep:90m light:223m rem:113m wake:49m synced 19:41 ET');
INSERT INTO recovery VALUES('2026-03-31',94.0,2.89999999999999991,3847,0,NULL,63,42.0,NULL,'FITBIT','synced 19:41 ET');
INSERT INTO recovery VALUES('2026-04-01',91.0,7.70000000000000017,13819,117,NULL,63,96.0,8.5,'FITBIT','deep:79m light:273m rem:108m wake:47m synced 19:42 ET');
INSERT INTO recovery VALUES('2026-04-02',91.0,5.09999999999999964,6870,27,NULL,62,80.0,5.59999999999999964,'FITBIT','deep:90m light:140m rem:74m wake:31m synced 19:42 ET');
INSERT INTO recovery VALUES('2026-04-03',NULL,NULL,24696,245,NULL,63,NULL,NULL,'FITBIT','synced 19:42 ET');
INSERT INTO recovery VALUES('2026-04-04',83.0,5.79999999999999982,698,0,NULL,63,82.0,7.0,'FITBIT','deep:89m light:175m rem:86m wake:72m');
INSERT INTO recovery VALUES('2026-04-05',93.0,7.0,6841,36,NULL,64,92.0,7.5,'FITBIT','deep:87m light:243m rem:87m wake:30m synced 20:13 ET');
INSERT INTO recovery VALUES('2026-04-06',91.0,4.70000000000000017,8876,48,NULL,63,77.0,5.09999999999999964,'FITBIT','deep:60m light:161m rem:57m wake:27m synced 22:33 ET');
INSERT INTO recovery VALUES('2026-04-07',NULL,NULL,12449,102,NULL,63,NULL,NULL,'FITBIT','synced 10:16 ET');
INSERT INTO recovery VALUES('2026-04-08',93.0,4.90000000000000035,4124,18,NULL,61,79.0,5.29999999999999982,'FITBIT','synced 10:16 ET');
INSERT INTO recovery VALUES('2026-04-09',92.0,6.5,4952,55,NULL,60,89.0,7.09999999999999964,'FITBIT','synced 10:16 ET');
INSERT INTO recovery VALUES('2026-04-10',NULL,NULL,6640,41,NULL,61,NULL,NULL,'FITBIT','synced 10:16 ET');
INSERT INTO recovery VALUES('2026-04-11',95.0,5.29999999999999982,6764,28,NULL,63,82.0,5.59999999999999964,'FITBIT','synced 10:16 ET');
INSERT INTO recovery VALUES('2026-04-12',92.0,4.90000000000000035,15101,146,NULL,64,79.0,5.29999999999999982,'FITBIT','synced 09:11 ET');
INSERT INTO recovery VALUES('2026-04-13',92.0,8.09999999999999964,12633,123,NULL,63,98.0,8.80000000000000071,'FITBIT','synced 16:00 ET');
INSERT INTO recovery VALUES('2026-04-14',94.0,5.90000000000000035,14070,89,NULL,62,85.0,6.29999999999999982,'FITBIT','synced 16:00 ET');
INSERT INTO recovery VALUES('2026-04-15',88.0,5.0,12126,131,NULL,62,78.0,5.70000000000000017,'FITBIT','synced 16:00 ET');
INSERT INTO recovery VALUES('2026-04-16',94.0,7.70000000000000017,10887,74,NULL,64,97.0,8.19999999999999929,'FITBIT','synced 11:00 ET');
INSERT INTO recovery VALUES('2026-04-17',NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,'FITBIT','synced 11:00 ET');
CREATE TABLE routine (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    effective_from  TEXT    NOT NULL,                    -- YYYY-MM-DD
    effective_to    TEXT,                                -- NULL = current
    day_of_week     INTEGER NOT NULL,                    -- 0=Mon .. 6=Sun (ISO)
    session_type    TEXT    NOT NULL,                    -- BRO_SPLIT_LEGS | REST | etc.
    exercises_json  TEXT    NOT NULL,                    -- JSON array of exercise names
    notes           TEXT,
    CHECK (day_of_week BETWEEN 0 AND 6)
) STRICT;
CREATE TABLE user_facts (
    key         TEXT    PRIMARY KEY,
    value       TEXT    NOT NULL,
    updated_at  TEXT    NOT NULL
) STRICT;
INSERT INTO user_facts VALUES('height_cm','171.5','2026-04-12');
INSERT INTO user_facts VALUES('birth_date','1984-04-14','2026-04-12');
INSERT INTO user_facts VALUES('goal_bf_pct','15','2026-04-12');
INSERT INTO user_facts VALUES('goal_weight_lbs','150','2026-04-12');
INSERT INTO user_facts VALUES('calorie_goal','1200','2026-04-14');
INSERT INTO user_facts VALUES('protein_goal_g','180','2026-04-14');
INSERT INTO user_facts VALUES('sleep_hours_goal','7','2026-04-14');
CREATE TABLE events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT    NOT NULL,                       -- ISO8601 with tz offset
    kind         TEXT    NOT NULL,
    payload_json TEXT    NOT NULL,                       -- free-form per kind
    user_msg_id  TEXT                                    -- Telegram msg id, nullable
) STRICT;
INSERT INTO events VALUES(1,'2026-04-12T21:20:39.955343-04:00','handler_call','{"handler": "log_workout", "date": "2026-04-12", "n_exercises": 1, "total_volume": 4125.0, "session_type": "BRO_SPLIT"}',NULL);
INSERT INTO events VALUES(2,'2026-04-12T21:20:40.267985-04:00','handler_call','{"handler": "log_workout", "date": "2026-04-12", "n_exercises": 1, "total_volume": 4725.0, "session_type": "BRO_SPLIT"}',NULL);
INSERT INTO events VALUES(3,'2026-04-12T21:20:40.496360-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-12", "weight_lbs": 172.5, "source": "TELEGRAM"}',NULL);
INSERT INTO events VALUES(4,'2026-04-12T21:20:40.711521-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-12", "weight_lbs": 170.0, "source": "RENPHO"}',NULL);
INSERT INTO events VALUES(5,'2026-04-12T21:20:41.022347-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-12", "calories": 2100.0, "protein_g": 170.0}',NULL);
INSERT INTO events VALUES(6,'2026-04-12T21:20:41.352412-04:00','handler_call','{"handler": "rename_exercise", "old_name": "Pull Up", "new_name": "Pull Ups", "rows_updated": 1}',NULL);
INSERT INTO events VALUES(7,'2026-04-12T21:20:41.612958-04:00','handler_call','{"handler": "edit_weight", "date": "2026-04-10", "weight_lbs": 171.5}',NULL);
INSERT INTO events VALUES(8,'2026-04-12T21:49:10.567150-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-12", "weight_lbs": 173.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(9,'2026-04-12T21:49:12.758181-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-12", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(10,'2026-04-12T21:49:13.503667-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-12", "calories": 602.0, "protein_g": 29.0}',NULL);
INSERT INTO events VALUES(11,'2026-04-13T02:00:06.759871-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(12,'2026-04-13T08:42:01.148547-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(13,'2026-04-13T08:42:03.508653-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(14,'2026-04-13T09:11:14.776659-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-12", "weight_lbs": 173.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(15,'2026-04-13T09:11:16.606175-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-12", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(16,'2026-04-13T09:11:16.969388-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-12", "calories": 3542.0, "protein_g": 144.0}',NULL);
INSERT INTO events VALUES(17,'2026-04-13T09:14:56.068153-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(18,'2026-04-13T09:14:57.564887-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(19,'2026-04-13T09:14:58.060727-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-13", "calories": 220.0, "protein_g": 16.0}',NULL);
INSERT INTO events VALUES(20,'2026-04-13T09:16:47.761721-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(21,'2026-04-13T09:16:49.755561-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(22,'2026-04-13T09:16:50.117873-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-13", "calories": 220.0, "protein_g": 16.0}',NULL);
INSERT INTO events VALUES(23,'2026-04-13T10:16:09.445355-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-07", "weight_lbs": 173.3, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(24,'2026-04-13T10:16:11.751533-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-07", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(25,'2026-04-13T10:16:12.186148-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-07", "calories": 1402.0, "protein_g": 172.0}',NULL);
INSERT INTO events VALUES(26,'2026-04-13T10:16:12.766790-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-08", "weight_lbs": 173.1, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(27,'2026-04-13T10:16:14.707336-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-08", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(28,'2026-04-13T10:16:15.222392-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-08", "calories": 2435.0, "protein_g": 160.0}',NULL);
INSERT INTO events VALUES(29,'2026-04-13T10:16:15.867905-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-09", "weight_lbs": 172.8, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(30,'2026-04-13T10:16:17.318525-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-09", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(31,'2026-04-13T10:16:17.662942-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-09", "calories": 1623.0, "protein_g": 105.0}',NULL);
INSERT INTO events VALUES(32,'2026-04-13T10:16:18.166042-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-10", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(33,'2026-04-13T10:16:21.090536-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-10", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(34,'2026-04-13T10:16:21.430223-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-10", "calories": 3132.0, "protein_g": 127.0}',NULL);
INSERT INTO events VALUES(35,'2026-04-13T10:16:21.906529-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-11", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(36,'2026-04-13T10:16:23.498659-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-11", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(37,'2026-04-13T10:16:23.895246-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-11", "calories": 3399.0, "protein_g": 119.0}',NULL);
INSERT INTO events VALUES(38,'2026-04-14T08:35:48.284687-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(39,'2026-04-14T08:35:50.800617-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(40,'2026-04-14T08:35:51.519231-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-13", "calories": 1813.0, "protein_g": 140.0}',NULL);
INSERT INTO events VALUES(41,'2026-04-14T08:35:52.207700-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(42,'2026-04-14T08:35:55.614182-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(43,'2026-04-14T11:00:02.258220-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(44,'2026-04-14T11:00:06.194351-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(45,'2026-04-14T11:00:07.664694-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-13", "calories": 1813.0, "protein_g": 140.0}',NULL);
INSERT INTO events VALUES(46,'2026-04-14T11:00:09.149238-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(47,'2026-04-14T11:00:14.898084-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(48,'2026-04-14T16:00:02.259430-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-13", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(49,'2026-04-14T16:00:10.387428-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-13", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(50,'2026-04-14T16:00:13.100411-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-13", "calories": 1813.0, "protein_g": 140.0}',NULL);
INSERT INTO events VALUES(51,'2026-04-14T16:00:13.519692-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(52,'2026-04-14T16:00:17.132629-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(53,'2026-04-14T16:00:17.523798-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-14", "calories": 1304.0, "protein_g": 146.0}',NULL);
INSERT INTO events VALUES(54,'2026-04-15T02:00:03.582222-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(55,'2026-04-15T02:00:12.660565-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(56,'2026-04-15T02:00:13.902978-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-14", "calories": 1304.0, "protein_g": 146.0}',NULL);
INSERT INTO events VALUES(57,'2026-04-15T02:00:20.861622-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(58,'2026-04-15T02:00:21.510878-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 954.0, "protein_g": 114.0}',NULL);
INSERT INTO events VALUES(59,'2026-04-15T11:00:04.632522-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(60,'2026-04-15T11:00:11.122147-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(61,'2026-04-15T11:00:11.772362-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-14", "calories": 1304.0, "protein_g": 146.0}',NULL);
INSERT INTO events VALUES(62,'2026-04-15T11:00:12.423929-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-15", "weight_lbs": 171.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(63,'2026-04-15T11:00:14.848330-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(64,'2026-04-15T11:00:15.634772-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 1304.0, "protein_g": 136.0}',NULL);
INSERT INTO events VALUES(65,'2026-04-15T16:00:04.479378-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-14", "weight_lbs": 175.9, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(66,'2026-04-15T16:00:06.073538-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-14", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(67,'2026-04-15T16:00:07.740467-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-14", "calories": 1304.0, "protein_g": 146.0}',NULL);
INSERT INTO events VALUES(68,'2026-04-15T16:00:08.169125-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-15", "weight_lbs": 171.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(69,'2026-04-15T16:00:10.861689-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(70,'2026-04-15T16:00:12.824469-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 1304.0, "protein_g": 136.0}',NULL);
INSERT INTO events VALUES(71,'2026-04-16T02:00:09.289714-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(72,'2026-04-16T02:00:11.137092-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 2037.0, "protein_g": 110.0}',NULL);
INSERT INTO events VALUES(73,'2026-04-16T02:00:15.445376-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(74,'2026-04-16T02:00:16.143235-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 908.0, "protein_g": 107.0}',NULL);
INSERT INTO events VALUES(75,'2026-04-16T10:08:20.251128-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-15", "weight_lbs": 171.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(76,'2026-04-16T10:08:28.025050-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(77,'2026-04-16T10:08:28.694324-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 2037.0, "protein_g": 110.0}',NULL);
INSERT INTO events VALUES(78,'2026-04-16T10:08:29.426651-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-16", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(79,'2026-04-16T10:08:32.842175-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(80,'2026-04-16T10:08:33.582683-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 1098.0, "protein_g": 128.0}',NULL);
INSERT INTO events VALUES(81,'2026-04-16T11:00:03.915182-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-15", "weight_lbs": 171.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(82,'2026-04-16T11:00:11.178328-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(83,'2026-04-16T11:00:11.613680-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 2037.0, "protein_g": 110.0}',NULL);
INSERT INTO events VALUES(84,'2026-04-16T11:00:12.012679-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-16", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(85,'2026-04-16T11:00:13.457615-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(86,'2026-04-16T11:00:13.907123-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 1098.0, "protein_g": 128.0}',NULL);
INSERT INTO events VALUES(87,'2026-04-16T16:00:02.439642-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-15", "weight_lbs": 171.7, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(88,'2026-04-16T16:00:04.702904-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-15", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(89,'2026-04-16T16:00:05.073905-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-15", "calories": 2037.0, "protein_g": 110.0}',NULL);
INSERT INTO events VALUES(90,'2026-04-16T16:00:05.425992-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-16", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(91,'2026-04-16T16:00:09.678175-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(92,'2026-04-16T16:00:15.548842-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 1230.0, "protein_g": 135.0}',NULL);
INSERT INTO events VALUES(93,'2026-04-17T02:00:08.191534-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-16", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(94,'2026-04-17T02:00:16.299151-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(95,'2026-04-17T02:00:17.353498-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 1574.0, "protein_g": 168.0}',NULL);
INSERT INTO events VALUES(96,'2026-04-17T02:00:20.645026-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-17", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(97,'2026-04-17T02:00:21.302392-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-17", "calories": 1055.0, "protein_g": 155.0}',NULL);
INSERT INTO events VALUES(98,'2026-04-17T11:00:02.994890-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-16", "weight_lbs": 172.0, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(99,'2026-04-17T11:00:10.304070-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-16", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(100,'2026-04-17T11:00:11.220030-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-16", "calories": 1574.0, "protein_g": 168.0}',NULL);
INSERT INTO events VALUES(101,'2026-04-17T11:00:11.949430-04:00','handler_call','{"handler": "log_weight", "date": "2026-04-17", "weight_lbs": 173.1, "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(102,'2026-04-17T11:00:14.414684-04:00','handler_call','{"handler": "log_recovery", "date": "2026-04-17", "source": "FITBIT"}',NULL);
INSERT INTO events VALUES(103,'2026-04-17T11:00:14.958425-04:00','handler_call','{"handler": "log_nutrition", "date": "2026-04-17", "calories": 992.0, "protein_g": 130.0}',NULL);
DELETE FROM sqlite_sequence;
INSERT INTO sqlite_sequence VALUES('workout',30);
INSERT INTO sqlite_sequence VALUES('cardio',3);
INSERT INTO sqlite_sequence VALUES('events',103);
CREATE INDEX idx_workout_date       ON workout(date);
CREATE INDEX idx_workout_exercise   ON workout(exercise);
CREATE INDEX idx_workout_date_ex    ON workout(date, exercise);
CREATE INDEX idx_cardio_date ON cardio(date);
CREATE INDEX idx_routine_active ON routine(effective_from, effective_to);
CREATE INDEX idx_events_ts    ON events(ts);
CREATE INDEX idx_events_kind  ON events(kind);
CREATE VIEW latest_body_scan AS
SELECT * FROM body_scan ORDER BY date DESC LIMIT 1;
CREATE VIEW latest_weight AS
SELECT * FROM body_metrics ORDER BY date DESC LIMIT 1;
CREATE VIEW active_routine AS
SELECT * FROM routine
WHERE effective_to IS NULL
   OR effective_to >= date('now');
COMMIT;
