-- Gaokao volunteer application Agent core SQLite schema and mock data.
-- Mock data is for development/testing only. It does NOT represent real admission data.
-- Initial scope: Chongqing, ordinary undergraduate batch, Physics/History tracks.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS recommendation_case;
DROP TABLE IF EXISTS school_major_profile;
DROP TABLE IF EXISTS subject_requirement;
DROP TABLE IF EXISTS score_rank_table;
DROP TABLE IF EXISTS admission_history;

CREATE TABLE admission_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL CHECK (year BETWEEN 2021 AND 2026),
    province TEXT NOT NULL DEFAULT '重庆',
    subject_type TEXT NOT NULL CHECK (subject_type IN ('物理', '历史')),
    batch TEXT NOT NULL CHECK (batch IN ('本科批', '专科批', '提前批')),
    school_code TEXT NOT NULL,
    school_name TEXT NOT NULL,
    major_group_code TEXT,
    major_code TEXT NOT NULL,
    major_name TEXT NOT NULL,
    major_category TEXT,
    discipline_category TEXT,
    admission_type TEXT NOT NULL CHECK (
        admission_type IN ('普通类', '中外合作', '民族班', '预科', '专项')
    ),
    min_score INTEGER NOT NULL CHECK (min_score BETWEEN 0 AND 750),
    min_rank INTEGER NOT NULL CHECK (min_rank > 0),
    plan_count INTEGER CHECK (plan_count IS NULL OR plan_count >= 0),
    source_url TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK (source_type IN ('official', 'third_party', 'manual_verified')),
    confidence TEXT NOT NULL CHECK (confidence IN ('high', 'medium', 'low')),
    risk_notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE score_rank_table (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL CHECK (year BETWEEN 2021 AND 2026),
    province TEXT NOT NULL DEFAULT '重庆',
    subject_type TEXT NOT NULL CHECK (subject_type IN ('物理', '历史')),
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 750),
    rank_min INTEGER NOT NULL CHECK (rank_min > 0),
    rank_max INTEGER NOT NULL CHECK (rank_max >= rank_min),
    same_score_count INTEGER NOT NULL CHECK (same_score_count >= 0),
    cumulative_count INTEGER NOT NULL CHECK (cumulative_count >= rank_max),
    batch_line_score INTEGER NOT NULL CHECK (batch_line_score BETWEEN 0 AND 750),
    above_batch_line_count INTEGER NOT NULL CHECK (above_batch_line_count > 0),
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subject_requirement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT NOT NULL,
    major_name TEXT NOT NULL,
    major_category TEXT,
    requirement_year INTEGER NOT NULL CHECK (requirement_year BETWEEN 2021 AND 2026),
    first_subject_required TEXT NOT NULL CHECK (
        first_subject_required IN ('物理', '历史', '物理或历史均可')
    ),
    second_subjects_required TEXT NOT NULL DEFAULT '不限',
    requirement_text TEXT NOT NULL,
    source_url TEXT NOT NULL,
    effective_from INTEGER NOT NULL CHECK (effective_from BETWEEN 2021 AND 2026),
    effective_to INTEGER CHECK (effective_to IS NULL OR effective_to BETWEEN effective_from AND 2030),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE school_major_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    school_name TEXT NOT NULL,
    major_name TEXT NOT NULL,
    discipline_category TEXT,
    employment_direction TEXT,
    postgraduate_direction TEXT,
    subject_requirement_summary TEXT,
    risk_notes TEXT,
    source_url TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE recommendation_case (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_name TEXT NOT NULL,
    province TEXT NOT NULL DEFAULT '重庆',
    score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 750),
    rank INTEGER,
    subject_type TEXT NOT NULL CHECK (subject_type IN ('物理', '历史')),
    second_subjects TEXT NOT NULL,
    target_region TEXT,
    major_interest TEXT,
    career_goal TEXT,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('保守', '均衡', '激进')),
    accept_sino_foreign INTEGER NOT NULL DEFAULT 0 CHECK (accept_sino_foreign IN (0, 1)),
    expected_behavior TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_admission_year_track_batch
    ON admission_history (year, province, subject_type, batch);

CREATE INDEX idx_admission_school_major
    ON admission_history (school_name, major_name);

CREATE INDEX idx_admission_rank
    ON admission_history (subject_type, batch, min_rank);

CREATE INDEX idx_score_rank_lookup
    ON score_rank_table (year, province, subject_type, score);

CREATE INDEX idx_subject_requirement_lookup
    ON subject_requirement (school_name, major_name, requirement_year);

CREATE INDEX idx_profile_lookup
    ON school_major_profile (school_name, major_name);

INSERT INTO admission_history (
    year, province, subject_type, batch, school_code, school_name,
    major_group_code, major_code, major_name, major_category, discipline_category,
    admission_type, min_score, min_rank, plan_count, source_url, source_type,
    confidence, risk_notes
) VALUES
-- 2025 Physics mock records
(2025, '重庆', '物理', '本科批', '10611', '重庆大学', 'CQ-10611-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 626, 9200, 72, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', 'Mock 数据；实际需核验 2025 官方投档表和 2026 招生章程'),
(2025, '重庆', '物理', '本科批', '10611', '重庆大学', 'CQ-10611-P02', '0828', '建筑类', '建筑类', '工学', '民族班', 598, 24500, 6, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '民族班资格限制，不能混入普通类推荐'),
(2025, '重庆', '物理', '本科批', '10635', '西南大学', 'CQ-10635-P01', '0701', '数学类', '数学类', '理学', '普通类', 602, 21000, 64, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '位次相对稳定，可作为稳妥候选的样例'),
(2025, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 588, 18500, 220, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '计算机类通常要求物理+化学，需以 2026 章程强校验'),
(2025, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P02', '0807', '电子信息类', '电子信息类', '工学', '普通类', 580, 22800, 260, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', 'Mock 数据；专业组可能每年调整'),
(2025, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P03', '0809H', '软件工程(中外合作办学)', '计算机类', '工学', '中外合作', 548, 41000, 80, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '高学费中外合作，用户未接受时必须过滤'),
(2025, '重庆', '物理', '本科批', '10631', '重庆医科大学', 'CQ-10631-P01', '100201K', '临床医学', '临床医学类', '医学', '普通类', 612, 13200, 190, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '医学类强依赖物理+化学和体检限制核验'),
(2025, '重庆', '物理', '本科批', '10631', '重庆医科大学', 'CQ-10631-P02', '1007', '药学类', '药学类', '医学', '普通类', 571, 28500, 96, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '需核验化学要求与色盲色弱限制'),
(2025, '重庆', '物理', '本科批', '10618', '重庆交通大学', 'CQ-10618-P01', '0802', '机械类', '机械类', '工学', '普通类', 552, 39200, 180, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '传统工科，通常需物理+化学'),
(2025, '重庆', '物理', '本科批', '11660', '重庆理工大学', 'CQ-11660-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 562, 33500, 200, 'https://www.cqksy.cn/mock/2025/physics', 'manual_verified', 'medium', '位次波动中等，适合测试稳/保边界'),
-- 2024 Physics mock records
(2024, '重庆', '物理', '本科批', '10611', '重庆大学', 'CQ-10611-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 623, 9800, 70, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据；实际需核验官方投档表'),
(2024, '重庆', '物理', '本科批', '10635', '西南大学', 'CQ-10635-P01', '0701', '数学类', '数学类', '理学', '普通类', 599, 21800, 62, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 585, 19600, 215, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P02', '0807', '电子信息类', '电子信息类', '工学', '普通类', 576, 23800, 250, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '物理', '本科批', '10617', '重庆邮电大学', 'CQ-10617-P03', '0809H', '软件工程(中外合作办学)', '计算机类', '工学', '中外合作', 544, 43000, 80, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', '高学费中外合作，用户未接受时必须过滤'),
(2024, '重庆', '物理', '本科批', '10631', '重庆医科大学', 'CQ-10631-P01', '100201K', '临床医学', '临床医学类', '医学', '普通类', 609, 14100, 185, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '物理', '本科批', '10618', '重庆交通大学', 'CQ-10618-P01', '0802', '机械类', '机械类', '工学', '普通类', 550, 40500, 176, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '物理', '本科批', '11660', '重庆理工大学', 'CQ-11660-P01', '0809', '计算机类', '计算机类', '工学', '普通类', 559, 34800, 195, 'https://www.cqksy.cn/mock/2024/physics', 'manual_verified', 'medium', 'Mock 数据'),
-- History track mock records
(2025, '重庆', '历史', '本科批', '10635', '西南大学', 'CQ-10635-H01', '0501', '中国语言文学类', '中国语言文学类', '文学', '普通类', 584, 3100, 58, 'https://www.cqksy.cn/mock/2025/history', 'manual_verified', 'medium', '师范/中文方向需区分是否公费师范或普通类'),
(2025, '重庆', '历史', '本科批', '10637', '重庆师范大学', 'CQ-10637-H01', '050101', '汉语言文学(师范)', '中国语言文学类', '文学', '普通类', 548, 8700, 120, 'https://www.cqksy.cn/mock/2025/history', 'manual_verified', 'medium', '师范类热门，位次可能波动'),
(2025, '重庆', '历史', '本科批', '10637', '重庆师范大学', 'CQ-10637-H02', '0305', '思想政治教育(师范)', '马克思主义理论类', '法学', '普通类', 542, 9800, 80, 'https://www.cqksy.cn/mock/2025/history', 'manual_verified', 'medium', '可能要求历史+政治，需核验 2026 章程'),
(2025, '重庆', '历史', '本科批', '10635', '西南大学', 'CQ-10635-H02', '0502H', '英语(中外合作办学)', '外国语言文学类', '文学', '中外合作', 528, 14500, 45, 'https://www.cqksy.cn/mock/2025/history', 'manual_verified', 'medium', '高学费中外合作，用户未接受时必须过滤'),
(2024, '重庆', '历史', '本科批', '10635', '西南大学', 'CQ-10635-H01', '0501', '中国语言文学类', '中国语言文学类', '文学', '普通类', 581, 3350, 56, 'https://www.cqksy.cn/mock/2024/history', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '历史', '本科批', '10637', '重庆师范大学', 'CQ-10637-H01', '050101', '汉语言文学(师范)', '中国语言文学类', '文学', '普通类', 544, 9200, 118, 'https://www.cqksy.cn/mock/2024/history', 'manual_verified', 'medium', 'Mock 数据'),
(2024, '重庆', '历史', '本科批', '10637', '重庆师范大学', 'CQ-10637-H02', '0305', '思想政治教育(师范)', '马克思主义理论类', '法学', '普通类', 538, 10400, 78, 'https://www.cqksy.cn/mock/2024/history', 'manual_verified', 'medium', 'Mock 数据');

INSERT INTO score_rank_table (
    year, province, subject_type, score, rank_min, rank_max, same_score_count,
    cumulative_count, batch_line_score, above_batch_line_count, source_url
) VALUES
(2025, '重庆', '物理', 630, 7900, 8600, 701, 8600, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 620, 10400, 11300, 901, 11300, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 610, 13600, 14800, 1201, 14800, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 600, 17600, 19000, 1401, 19000, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 590, 21200, 22900, 1701, 22900, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 580, 25100, 27200, 2101, 27200, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 560, 33000, 35800, 2801, 35800, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2025, '重庆', '物理', 540, 43000, 46200, 3201, 46200, 428, 72000, 'https://www.cqksy.cn/mock/2025/score-rank-physics'),
(2024, '重庆', '物理', 630, 8300, 9000, 701, 9000, 427, 70000, 'https://www.cqksy.cn/mock/2024/score-rank-physics'),
(2024, '重庆', '物理', 620, 10900, 11800, 901, 11800, 427, 70000, 'https://www.cqksy.cn/mock/2024/score-rank-physics'),
(2024, '重庆', '物理', 600, 18100, 19600, 1501, 19600, 427, 70000, 'https://www.cqksy.cn/mock/2024/score-rank-physics'),
(2024, '重庆', '物理', 580, 26000, 28200, 2201, 28200, 427, 70000, 'https://www.cqksy.cn/mock/2024/score-rank-physics'),
(2024, '重庆', '物理', 560, 34000, 37000, 3001, 37000, 427, 70000, 'https://www.cqksy.cn/mock/2024/score-rank-physics'),
(2025, '重庆', '历史', 585, 2800, 3200, 401, 3200, 428, 28500, 'https://www.cqksy.cn/mock/2025/score-rank-history'),
(2025, '重庆', '历史', 560, 6100, 6900, 801, 6900, 428, 28500, 'https://www.cqksy.cn/mock/2025/score-rank-history'),
(2025, '重庆', '历史', 545, 9100, 10100, 1001, 10100, 428, 28500, 'https://www.cqksy.cn/mock/2025/score-rank-history'),
(2025, '重庆', '历史', 530, 13200, 14900, 1701, 14900, 428, 28500, 'https://www.cqksy.cn/mock/2025/score-rank-history'),
(2024, '重庆', '历史', 585, 3000, 3450, 451, 3450, 428, 27800, 'https://www.cqksy.cn/mock/2024/score-rank-history'),
(2024, '重庆', '历史', 545, 9400, 10400, 1001, 10400, 428, 27800, 'https://www.cqksy.cn/mock/2024/score-rank-history');

INSERT INTO subject_requirement (
    school_name, major_name, major_category, requirement_year,
    first_subject_required, second_subjects_required, requirement_text,
    source_url, effective_from, effective_to
) VALUES
('重庆大学', '计算机类', '计算机类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqu-computer', 2024, NULL),
('重庆邮电大学', '计算机类', '计算机类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqupt-computer', 2024, NULL),
('重庆邮电大学', '电子信息类', '电子信息类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqupt-electronics', 2024, NULL),
('重庆医科大学', '临床医学', '临床医学类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考；另需核验体检限制。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqmu-clinical', 2024, NULL),
('重庆医科大学', '药学类', '药学类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqmu-pharmacy', 2024, NULL),
('重庆交通大学', '机械类', '机械类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqjtu-mechanical', 2024, NULL),
('重庆理工大学', '计算机类', '计算机类', 2026, '物理', '化学', '物理、化学 2 门科目均须选考方可报考。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqut-computer', 2024, NULL),
('西南大学', '中国语言文学类', '中国语言文学类', 2026, '历史', '不限', '首选历史，通常再选科目不限；以 2026 招生章程为准。', 'https://gaokao.chsi.com.cn/mock/subject/2026/swu-chinese', 2024, NULL),
('重庆师范大学', '汉语言文学(师范)', '中国语言文学类', 2026, '历史', '不限', '首选历史，通常再选科目不限；师范方向需核验专业备注。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqnu-chinese', 2024, NULL),
('重庆师范大学', '思想政治教育(师范)', '马克思主义理论类', 2026, '历史', '政治', '首选历史，再选思想政治。', 'https://gaokao.chsi.com.cn/mock/subject/2026/cqnu-politics', 2024, NULL);

INSERT INTO school_major_profile (
    school_name, major_name, discipline_category, employment_direction,
    postgraduate_direction, subject_requirement_summary, risk_notes, source_url
) VALUES
('重庆大学', '计算机类', '工学', '软件开发、人工智能、云计算、数据平台、国企/互联网技术岗', '计算机科学与技术、软件工程、人工智能、网络空间安全', '2024 起多数计算机相关专业要求物理+化学。', '热门专业位次波动和报考热度高，不宜仅按上一年低位次判断。', 'https://gaokao.chsi.com.cn/mock/profile/computer'),
('重庆邮电大学', '计算机类', '工学', '通信互联网、软件开发、信息安全、嵌入式与平台研发', '计算机、电子信息、软件工程', '物理+化学。', '行业热度高，需结合院校专业组变化和中外合作标签过滤。', 'https://gaokao.chsi.com.cn/mock/profile/computer'),
('重庆邮电大学', '电子信息类', '工学', '通信设备、芯片测试、嵌入式、运营商、电子制造', '电子科学与技术、信息与通信工程', '物理+化学。', '课程硬核，数学/物理基础弱的学生需谨慎。', 'https://gaokao.chsi.com.cn/mock/profile/electronics'),
('重庆医科大学', '临床医学', '医学', '医院临床岗位、规培、医学科研、基层医疗', '临床医学、基础医学、公共卫生', '物理+化学，并需核验体检限制。', '学习周期长、深造压力大，色盲色弱等体检限制需重点核验。', 'https://gaokao.chsi.com.cn/mock/profile/clinical-medicine'),
('重庆医科大学', '药学类', '医学', '药企研发、医院药房、药品注册、药物分析', '药学、药理学、药物化学', '物理+化学。', '需核验色盲色弱限制和专业分流规则。', 'https://gaokao.chsi.com.cn/mock/profile/pharmacy'),
('重庆师范大学', '汉语言文学(师范)', '文学', '中小学语文教师、编辑出版、公务员、事业单位', '中国语言文学、教育学、学科语文', '首选历史，通常不限再选；以当年章程为准。', '师范岗位地区差异明显，需结合编制与城市偏好。', 'https://gaokao.chsi.com.cn/mock/profile/chinese-education'),
('重庆师范大学', '思想政治教育(师范)', '法学', '中学政治教师、党政机关、基层治理岗位', '马克思主义理论、教育学、学科思政', '历史+政治。', '若未选政治，需强拦截或红色风险提示。', 'https://gaokao.chsi.com.cn/mock/profile/political-education');

INSERT INTO recommendation_case (
    case_name, province, score, rank, subject_type, second_subjects,
    target_region, major_interest, career_goal, risk_level,
    accept_sino_foreign, expected_behavior
) VALUES
('物理不选化学想报计算机', '重庆', 590, 22000, '物理', '生物,地理', '重庆', '计算机科学与技术', '软件开发', '均衡', 0, '应触发物理+化学选科风险，计算机类不得直接进入强推荐池。'),
('物理化学考生位次两万附近', '重庆', 596, 20000, '物理', '化学,生物', '重庆', '电子信息,计算机', '通信互联网', '均衡', 0, '应返回重庆邮电大学电子信息类、西南大学数学类等冲稳保候选，并过滤中外合作。'),
('历史类师范方向', '重庆', 548, 8800, '历史', '政治,地理', '重庆', '汉语言文学,思想政治教育', '中学教师', '保守', 0, '应返回重庆师范大学师范类候选，并核验思想政治教育的政治要求。'),
('接受中外合作的物理考生', '重庆', 552, 40000, '物理', '化学,生物', '重庆', '软件工程', '软件开发', '激进', 1, '允许出现中外合作候选，但报告必须提示学费和培养模式需人工核验。');

-- Verification query examples:
-- 1. Physics candidates around rank 20000, excluding Sino-foreign programs:
-- SELECT year, school_name, major_name, admission_type, min_score, min_rank
-- FROM admission_history
-- WHERE year = 2025 AND subject_type = '物理' AND batch = '本科批'
--   AND min_rank BETWEEN 15000 AND 26000
--   AND admission_type != '中外合作'
-- ORDER BY min_rank;
--
-- 2. Chongqing University of Posts and Telecommunications computer trend:
-- SELECT year, school_name, major_name, min_score, min_rank, source_type, confidence
-- FROM admission_history
-- WHERE school_name = '重庆邮电大学' AND major_name = '计算机类'
-- ORDER BY year;
--
-- 3. Clinical Medicine 2026 subject requirement:
-- SELECT school_name, major_name, requirement_year, requirement_text
-- FROM subject_requirement
-- WHERE major_name = '临床医学' AND requirement_year = 2026;
--
-- 4. Filter out Sino-foreign programs when the user does not accept them:
-- SELECT school_name, major_name, admission_type, min_score, min_rank
-- FROM admission_history
-- WHERE year = 2025 AND subject_type = '物理'
--   AND admission_type != '中外合作'
-- ORDER BY min_rank
-- LIMIT 10;
