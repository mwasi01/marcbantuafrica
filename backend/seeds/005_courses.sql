-- ============================================================
-- SEED 005 — LEARNING PLATFORM
-- ============================================================

-- ============================================================
-- COURSES
-- ============================================================
INSERT OR IGNORE INTO courses
    (id, title, slug, description, long_description, category, level, language,
     duration_minutes, lesson_count, is_free, published)
VALUES
    (1, 'Farm Management Fundamentals', 'farm-management-fundamentals',
     'Learn the core principles that separate profitable farms from struggling ones.',
     'This course covers the three pillars of farm management: clear planning, disciplined record keeping, and confident decision-making. You will learn how to treat your farm as a business and use data to grow your profit.',
     'Management', 'beginner', 'en', 180, 12, 1, 1),

    (2, 'Financial Literacy for Farmers', 'financial-literacy-farmers',
     'Understand costs, profits, margins, and how to make financial decisions with confidence.',
     'From reading your P&L to calculating break-even points, this course gives you the financial skills every farmer needs. No accounting background required.',
     'Finance', 'beginner', 'en', 120, 8, 1, 1),

    (3, 'Decision-Making for Farm Managers', 'decision-making-farm-managers',
     'Master break-even, marginal analysis, risk assessment, and investment decisions.',
     'Great farmers make great decisions. This course gives you frameworks used by professional farm managers to decide what to plant, when to invest, and how to manage risk.',
     'Management', 'intermediate', 'en', 150, 10, 1, 1),

    (4, 'Record Keeping That Grows Profit', 'record-keeping-grows-profit',
     'Practical, simple record-keeping systems for small and medium farms.',
     'Learn what to record, how to record it, and how to turn records into profit insights. Includes templates for crops, livestock, and finances.',
     'Operations', 'beginner', 'en', 90, 6, 1, 1),

    (5, 'Dairy Farming as a Business', 'dairy-farming-business',
     'From daily milk records to breeding decisions — run your dairy profitably.',
     'A deep dive into dairy enterprise management: feeding, health, breeding, records, milk quality, and marketing. Includes Kenyan case studies.',
     'Livestock', 'intermediate', 'en', 200, 14, 0, 1),

    (6, 'Maize Production Mastery', 'maize-production-mastery',
     'Maximize maize yields with proven agronomic and management practices.',
     'From variety selection to post-harvest handling. Learn how profitable Kenyan maize farmers plan, plant, protect, and sell their crop.',
     'Crops', 'beginner', 'en', 160, 10, 1, 1);

-- ============================================================
-- LESSONS (sample — Course 1 has 12 lessons)
-- ============================================================
INSERT OR IGNORE INTO lessons (course_id, title, content, order_num, duration_minutes)
VALUES
    (1, 'Why Most Farms Struggle', 'Introduction to the three pillars of farm management.', 1, 12),
    (1, 'Treating Your Farm as a Business', 'The mindset shift that changes everything.', 2, 15),
    (1, 'Understanding Your Costs', 'Fixed vs. variable. Direct vs. indirect.', 3, 18),
    (1, 'Introduction to Farm Records', 'What to record, when, and why.', 4, 15),
    (1, 'Planning Your Season', 'Step-by-step seasonal planning.', 5, 20),
    (1, 'Enterprise Budgets', 'Building your first budget.', 6, 18),
    (1, 'Cash Flow Basics', 'Why profit ≠ cash.', 7, 15),
    (1, 'Break-Even Analysis', 'Finding your minimum viable yield.', 8, 20),
    (1, 'Marginal Analysis', 'Deciding on the next acre or cow.', 9, 18),
    (1, 'Risk Management', 'Identifying and mitigating farm risks.', 10, 15),
    (1, 'Using Data to Decide', 'Turning records into action.', 11, 20),
    (1, 'Your Farm Business Plan', 'Putting it all together.', 12, 24),

    (2, 'Reading Your Profit & Loss', 'What P&L tells you about your farm.', 1, 15),
    (2, 'Understanding Your Costs', 'Deep dive into cost categories.', 2, 15),
    (2, 'Profit vs. Cash Flow', 'Why they are different.', 3, 15),
    (2, 'Gross Margin Analysis', 'Per enterprise profitability.', 4, 15),
    (2, 'Break-Even Points', 'Find your minimum.', 5, 15),
    (2, 'Loan Affordability', 'Can you service a loan?', 6, 15),
    (2, 'Investment Decisions', 'ROI and payback.', 7, 15),
    (2, 'Reading Financial Statements', 'Making sense of the numbers.', 8, 15);

-- Update lesson counts
UPDATE courses SET lesson_count = (SELECT COUNT(*) FROM lessons WHERE course_id = courses.id);

-- ============================================================
-- VIDEOS
-- ============================================================
INSERT OR IGNORE INTO videos (title, description, video_url, duration_seconds, category, language, published)
VALUES
    ('How to keep farm records that grow profit', 'Introduction to simple farm record-keeping.', 'https://stream.marcbantuafrica.com/video1', 765, 'Management', 'en', 1),
    ('Planning your season in 30 minutes', 'Step-by-step seasonal planning walkthrough.', 'https://stream.marcbantuafrica.com/video2', 500, 'Planning', 'en', 1),
    ('Break-even analysis for small farms', 'Calculate your break-even point.', 'https://stream.marcbantuafrica.com/video3', 910, 'Finance', 'en', 1),
    ('Dairy record keeping that pays', 'Simple dairy records for small herds.', 'https://stream.marcbantuafrica.com/video4', 630, 'Livestock', 'en', 1),
    ('Marginal analysis: is the next acre worth it?', 'Deciding on farm expansion.', 'https://stream.marcbantuafrica.com/video5', 1080, 'Decisions', 'en', 1),
    ('Using M-Pesa for farm payments', 'Recording mobile money transactions.', 'https://stream.marcbantuafrica.com/video6', 435, 'Finance', 'en', 1);

-- ============================================================
-- ENROLLMENTS (sample — assign courses to farmers)
-- ============================================================
INSERT OR IGNORE INTO enrollments (farmer_id, course_id, progress, completed)
VALUES
    ((SELECT id FROM farmers WHERE phone = '+254712345678'), 1, 65, 0),
    ((SELECT id FROM farmers WHERE phone = '+254712345678'), 4, 30, 0),
    ((SELECT id FROM farmers WHERE phone = '+254723456789'), 6, 100, 1),
    ((SELECT id FROM farmers WHERE phone = '+254734567890'), 1, 15, 0),
    ((SELECT id FROM farmers WHERE phone = '+254745678901'), 5, 45, 0),
    ((SELECT id FROM farmers WHERE phone = '+254756789012'), 2, 10, 0);

-- ============================================================
-- FORUM TOPICS
-- ============================================================
INSERT OR IGNORE INTO forum_topics (farmer_id, title, body, category, reply_count, view_count)
VALUES
    ((SELECT id FROM farmers WHERE phone = '+254712345678'),
     'Best dairy feed for high yield?',
     'I have 2 Friesian crosses producing 20L each. What feed combination gives the best yield without breaking the bank?',
     'Livestock', 12, 145),

    ((SELECT id FROM farmers WHERE phone = '+254723456789'),
     'Fall armyworm — what is working for you?',
     'Seeing armyworm in my maize despite spraying. What products or practices have worked for you this season?',
     'Pest Control', 8, 210),

    ((SELECT id FROM farmers WHERE phone = '+254745678901'),
     'How do you record casual labour costs?',
     'I hire casuals daily for weeding. How do you track their wages in your farm records?',
     'Records', 5, 87),

    ((SELECT id FROM farmers WHERE phone = '+254712345678'),
     'Maize prices — where are you selling?',
     'Nakuru market is at 45/kg. Anyone getting better prices elsewhere?',
     'Market', 15, 320);

-- ============================================================
-- FORUM REPLIES (sample)
-- ============================================================
INSERT OR IGNORE INTO forum_replies (topic_id, farmer_id, body, upvotes)
VALUES
    (1, (SELECT id FROM farmers WHERE phone = '+254723456789'),
     'I use dairy meal plus nappier grass and my cows hit 22L. Key is consistency and clean water.', 5),
    (1, (SELECT id FROM farmers WHERE phone = '+254745678901'),
     'Have you tried silage? Made a big difference for me in the dry season.', 3),
    (2, (SELECT id FROM farmers WHERE phone = '+254712345678'),
     'Ampligo 150 ZC works well if applied early. Spray at dusk for best results.', 7),
    (2, (SELECT id FROM farmers WHERE phone = '+254734567890'),
     'I use neem extract as preventive. Cheap and effective.', 4);

-- ============================================================
-- EXPERTS
-- ============================================================
INSERT OR IGNORE INTO experts (name, specialty, bio, phone, email, hourly_rate, languages, available)
VALUES
    ('Dr. Sarah Kamau', 'Dairy & Livestock',
     'Veterinarian with 15 years experience in dairy herd management.',
     '+254733111222', 'sarah.kamau@example.com', 3000, 'English, Swahili', 1),

    ('Mr. David Mutiso', 'Agronomy & Crops',
     'Agronomist specializing in maize, beans, and horticulture.',
     '+254733222333', 'david.mutiso@example.com', 2500, 'English, Swahili, Kikuyu', 1),

    ('Ms. Grace Wanjiru', 'Farm Finance',
     'Agricultural economist focused on smallholder financial management.',
     '+254733333444', 'grace.wanjiru@example.com', 3500, 'English, Swahili', 1),

    ('Dr. Peter Ochieng', 'Poultry',
     'Poultry specialist with focus on layer and broiler operations.',
     '+254733444555', 'peter.ochieng@example.com', 2800, 'English, Swahili, Dholuo', 0);

-- ============================================================
-- CHATBOT CONVERSATION (sample)
-- ============================================================
INSERT OR IGNORE INTO chatbot_conversations (farmer_id, session_id, title)
VALUES
    ((SELECT id FROM farmers WHERE phone = '+254712345678'), 'sess-demo-001', 'Break-even for maize');

INSERT OR IGNORE INTO chatbot_messages (conversation_id, role, message)
VALUES
    (1, 'user', 'How do I calculate break-even for my maize?'),
    (1, 'assistant', 'Divide your total fixed costs by the contribution margin per unit. For example, if fixed costs are KES 20,000, price is KES 45/kg, and variable cost is KES 15/kg, your break-even is 20,000 ÷ 30 = 667 kg. Use our Break-Even Calculator in the Decisions section for exact figures.'),
    (1, 'user', 'What if my price drops to 40?'),
    (1, 'assistant', 'At KES 40/kg with the same KES 15/kg variable cost, your contribution margin drops to KES 25/kg. Break-even rises to 20,000 ÷ 25 = 800 kg. That is 133 kg more you would need to sell. This is why price risk matters.');