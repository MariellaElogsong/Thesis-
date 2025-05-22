import pandas as pd
import random
import os
from datetime import datetime
from tabulate import tabulate
from collections import defaultdict
from flask import Flask, render_template, request, redirect

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), 'current')

@app.route('/faculty')
def faculty():
    df = pd.read_csv(os.path.join(UPLOAD_FOLDER, 'instructors.csv'))
    instructors = df['InstructorName'].tolist()  # Adjust column name as needed
    return render_template('faculty.html', instructors=instructors)

@app.route('/upload', methods=['POST'])
def upload():
    files = request.files.getlist('csvFile')
    allowed = {'instructors.csv', 'courses.csv', 'minorcourses.csv', 'rooms.csv'}
    for file in files:
        if file.filename in allowed:
            file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return redirect('/faculty')

@app.route('/new')
def new():
    return render_template('new.html')

if __name__ == '__main__':
    app.run(debug=True)

# === Load CSVs ===
courses_df = pd.read_csv(r'C:\Users\Mariella Elogsong\OneDrive\Documents\GitHub\Thesis-\current\courses.csv')
minorcourses_df = pd.read_csv(r'C:\Users\Mariella Elogsong\OneDrive\Documents\GitHub\Thesis-\current\minorcourses.csv')
instructors_df = pd.read_csv(r'C:\Users\Mariella Elogsong\OneDrive\Documents\GitHub\Thesis-\current\instructors.csv')
rooms_df = pd.read_csv(r'C:\Users\Mariella Elogsong\OneDrive\Documents\GitHub\Thesis-\current\rooms.csv')

# === Helpers ===
def parse_list(s, delimiter=';'):
    return [item.strip() for item in str(s).split(delimiter) if item.strip()]

def parse_days(day_str):
    day_map = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday",
        "Sun": "Sunday"
    }
    return [day_map.get(d.strip(), d.strip()) for d in str(day_str).split(';') if d.strip()]


def parse_time_range(time_str):
    try:
        start, end = time_str.strip().split('-')
        start_hour = int(datetime.strptime(start.strip(), "%H:%M").strftime("%H"))
        end_hour = int(datetime.strptime(end.strip(), "%H:%M").strftime("%H"))
        return start_hour, end_hour
    except:
        return 7, 17

def generate_time_blocks(start_hour, end_hour, duration):
    return [f"{h:02d}:00-{h + duration:02d}:00" for h in range(start_hour, end_hour - duration + 1)]

def get_year_group(section):
    parts = section.strip().split()
    return ' '.join(parts[:2]) if len(parts) >= 2 else section

def group_courses_by_year(courses):
    year_groups = {}
    for course in courses:
        year_key = get_year_group(course['Section'])
        if year_key not in year_groups:
            year_groups[year_key] = []
        year_groups[year_key].append(course)
    return year_groups

def time_to_range(time_str):
    start_str, end_str = time_str.split('-')
    start_hour = int(start_str.split(':')[0])
    end_hour = int(end_str.split(':')[0])
    return range(start_hour, end_hour)

def has_time_conflict(existing_blocks, new_range):
    for block in parse_list(existing_blocks):
        if not block:
            continue
        s, e = block.split('-')
        existing_range = range(int(s[:2]), int(e[:2]))
        if set(existing_range).intersection(new_range):
            return True
    return False

# === Expand Courses by Section ===
expanded_courses = []
for df, is_minor in [(courses_df, False), (minorcourses_df, True)]:
    for _, row in df.iterrows():
        sections = parse_list(row['Sections'])
        for section in sections:
            expanded_courses.append({
                'CourseCode': row['CourseCode'].strip(),
                'CourseName': row['CourseName'].strip(),
                'LectureHours': int(row['LectureHours']) if pd.notna(row['LectureHours']) else 0,
                'LabHours': int(row['LabHours']) if pd.notna(row['LabHours']) else 0,
                'RequiredCCL': row['RequiredCCL'],
                'SpecificLabRoom': row.get('SpecificLabRoom', ''),
                'Section': section.strip(),
                'LabNeedsRoom': str(row.get('LabNeedsRoom', 'True')).strip().lower() != 'false',
                'IsMinor': is_minor
            })

# === Group Courses by Year ===
year_groups = group_courses_by_year(expanded_courses)

# === Initialize Instructor Tracker ===
tracker = []
for _, row in instructors_df.iterrows():
    name = row['InstructorName']
    maxload = int(row['MaxLoad'])
    for day in parse_days(row['AvailableDays']):
        tracker.append({
            'Instructor': name,
            'Day': day,
            'AssignedTimeBlocks': '',
            'MaxLoad': maxload,
            'HoursUsed': 0
        })

instructor_tracker = pd.DataFrame(tracker)
global_load = {name: 0 for name in instructors_df['InstructorName']}
room_tracker = []
room_type_map = rooms_df.set_index('RoomID')['RoomType'].str.lower().to_dict()

# === Room Selection Logic ===
def select_room(course_code=None, session_type=None, specific_lab=None, lab_needs_room=True, required_ccl=False):
    session_type = session_type.lower() if session_type else ''
    if session_type == 'lab':
        if not lab_needs_room:
            # Needs a lecture room (lab session that does not require a real lab)
            room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lecture']
            if specific_lab:
                valid_rooms = [r.strip().lower() for r in specific_lab.split(';') if r]
                room_options = room_options[room_options['RoomID'].str.lower().isin(valid_rooms)]
            if not room_options.empty:
                return random.choice(room_options['RoomID'].tolist())
            return None
        if required_ccl and specific_lab:
            room_options = rooms_df[rooms_df['RoomID'].str.strip().str.lower() == specific_lab.strip().lower()]
            if not room_options.empty:
                return room_options.iloc[0]['RoomID']
            return None
        room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lab']
        if not room_options.empty:
            return random.choice(room_options['RoomID'].tolist())
        return None
    else:
        room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lecture']
        if not room_options.empty:
            return random.choice(room_options['RoomID'].tolist())
        return None
        room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lecture']
        if not room_options.empty:
            return random.choice(room_options['RoomID'].tolist())
        return None
        if not lab_needs_room:
            room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lecture']
            if not room_options.empty:
                return random.choice(room_options['RoomID'].tolist())
            return None
        room_options = rooms_df[rooms_df['RoomType'].str.strip().str.lower() == 'lab']
        if not room_options.empty:
            return random.choice(room_options['RoomID'].tolist())
        return None

def is_room_available(room, day, time):
    for entry in room_tracker:
        if entry['Room'] == room and entry['Day'] == day and entry['Time'] == time:
            return False
    return True

def mark_room_as_used(room, day, time, course):
    room_tracker.append({'Room': room, 'Day': day, 'Time': time, 'Course': course})


# === Run Scheduler and Save Output ===
def schedule_year(year, course_list):
    global instructor_tracker
    timetable = []

    for course in course_list:
        course_code = course['CourseCode'].strip().upper()
        course_name = course['CourseName']
        section = course['Section']
        lecture_hours = course['LectureHours']
        lab_hours = course['LabHours']
        specific_lab = str(course.get('SpecificLabRoom', '') or '').strip()
        lab_needs_room = course.get('LabNeedsRoom', True)
        required_ccl = str(course.get('RequiredCCL', '0')).strip() == '1'
        is_minor = course.get('IsMinor', False)
        is_first_or_second_year = any(
            section.upper().replace('-', ' ').strip().startswith(prefix)
            for prefix in ['BSCS 1', 'BSCS 2', 'BSIT 1', 'BSIT 2']
        )

        for session_type, hours_needed in [('Lecture', lecture_hours), ('Lab', lab_hours)]:
            if hours_needed == 0:
                continue

            # Allowed days
            if 'FITT' in course_code or 'NSTP' in course_code:
                allowed_days = ["Friday", "Saturday"]
            elif is_first_or_second_year and not ('FITT' in course_code or 'NSTP' in course_code):
                allowed_days = ["Monday", "Tuesday", "Wednesday", "Thursday"]
            else:
                allowed_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

            assigned = False

            # Try to assign qualified instructor
            eligible_instructors = instructors_df[instructors_df['CoursesCanTeach'].fillna('').apply(
                lambda x: any(course_code.replace(' ', '').upper() == c.strip().replace(' ', '').upper() for c in x.split(';'))
            )]

            for _, instr in eligible_instructors.iterrows():
                name = instr['InstructorName']
                available_days = parse_days(instr['AvailableDays'])
                start_hour, end_hour = parse_time_range(str(instr['AvailableTimes']))
                maxload = int(instr['MaxLoad'])

                if global_load[name] + hours_needed > maxload:
                    continue

                possible_blocks = generate_time_blocks(start_hour, end_hour, hours_needed)
                valid_days = [d for d in allowed_days if d in available_days]
                random.shuffle(valid_days)
                random.shuffle(possible_blocks)

                for day in valid_days:
                    if day not in available_days:
                        continue

                    row = instructor_tracker[
                        (instructor_tracker['Instructor'] == name) &
                        (instructor_tracker['Day'] == day)
                    ]

                    if row.empty:
                        continue

                    current_used = int(row['HoursUsed'].values[0])
                    assigned_blocks = row['AssignedTimeBlocks'].values[0]

                    if current_used + hours_needed > maxload:
                        continue

                    for time_block in possible_blocks:
                        if has_time_conflict(assigned_blocks, time_to_range(time_block)):
                            continue

                        room_id = select_room(course_code, session_type, specific_lab, lab_needs_room, required_ccl)
                        if room_id and is_room_available(room_id, day, time_block):
                            timetable.append({
                                'YearLevel': year,
                                'Section': section,
                                'Course': f"{course_code} - {course_name}",
                                'Session': session_type,
                                'Room': room_id,
                                'Day': day,
                                'Time': time_block,
                                'Instructor': name
                            })
                            updated_blocks = assigned_blocks + ';' + time_block if assigned_blocks else time_block
                            instructor_tracker.loc[
                                (instructor_tracker['Instructor'] == name) &
                                (instructor_tracker['Day'] == day),
                                ['AssignedTimeBlocks', 'HoursUsed']
                            ] = [updated_blocks, current_used + hours_needed]
                            global_load[name] += hours_needed
                            mark_room_as_used(room_id, day, time_block, course_code)
                            assigned = True
                            break
                    if assigned:
                        break
                if assigned:
                    break

            # Fallback if no instructor was assigned
            if not assigned:
                fallback_day = random.choice(allowed_days)
                fallback_start = random.randint(7, 16 - hours_needed)
                fallback_time_block = f"{fallback_start:02d}:00-{fallback_start + hours_needed:02d}:00"
                room_id = select_room(course_code, session_type, specific_lab, lab_needs_room, required_ccl)
                if room_id and is_room_available(room_id, fallback_day, fallback_time_block):
                    timetable.append({
                        'YearLevel': year,
                        'Section': section,
                        'Course': f"{course_code} - {course_name}",
                        'Session': session_type,
                        'Room': room_id,
                        'Day': fallback_day,
                        'Time': fallback_time_block,
                        'Instructor': 'Sample Instructor'
                    })
                    mark_room_as_used(room_id, fallback_day, fallback_time_block, course_code)

    return timetable




os.makedirs("output_schedule", exist_ok=True)
master_timetable = []
for year, group in sorted(year_groups.items()):
    print(f"\n📅 Scheduling {year} with {len(group)} sections...")
    year_timetable = schedule_year(year, group)
    df_year = pd.DataFrame(year_timetable)
    df_year.to_csv(f"output_schedule/timetable_{year.replace(' ', '_')}.csv", index=False)
    master_timetable.extend(year_timetable)
    print(f"✅ Done: Saved timetable_{year.replace(' ', '_')}.csv")

df_all = pd.DataFrame(master_timetable)
df_all.to_csv("final_timetable.csv", index=False)

# === Display Full Timetable Output ===
print("\n📋 Final Generated Timetable:\n")
print(tabulate(df_all, headers='keys', tablefmt='grid'))

# === Constraint Checker ===

instructor_courses = instructors_df.set_index('InstructorName')['CoursesCanTeach'].apply(parse_list).to_dict()
instructor_maxload = instructors_df.set_index('InstructorName')['MaxLoad'].astype(int).to_dict()

# 1. FITT/NSTP and 1st/2nd Year Day Constraint Check
fitt_nstp_violations = []
regular_day_violations = []
for _, row in df_all.iterrows():
    course_code = row['Course'].split('-')[0].strip().upper()
    day = row['Day']
    section = row['Section']

    if 'FITT' in course_code or 'NSTP' in course_code:
        if day not in ['Friday', 'Saturday']:
            fitt_nstp_violations.append(row)
    elif section.startswith(('BSCS 1', 'BSCS 2', 'BSIT 1', 'BSIT 2')):
        if day in ['Friday', 'Saturday']:
            regular_day_violations.append(row)

# 2. Instructor Qualification
invalid_qual = df_all[
    (df_all['Instructor'] != 'Sample Instructor') &
    (~df_all.apply(lambda row: row['Course'].split('-')[0].strip().upper() in
                   [c.strip().upper() for c in instructor_courses.get(row['Instructor'], [])], axis=1))
]

# 3. Instructor Max Load
instructor_hours = defaultdict(int)
for _, row in df_all.iterrows():
    if row['Instructor'] != 'Sample Instructor':
        start, end = parse_time_range(row['Time'])
        instructor_hours[row['Instructor']] += (end - start)

overloaded = [
    {'Instructor': instr, 'HoursUsed': used, 'MaxLoad': instructor_maxload.get(instr, 0)}
    for instr, used in instructor_hours.items()
    if used > instructor_maxload.get(instr, 0)
]

# 4. Instructor Time Conflicts
instructor_time_conflicts = df_all.groupby(['Instructor', 'Day', 'Time']).filter(
    lambda x: len(x) > 1 and x['Instructor'].iloc[0] != 'Sample Instructor'
)

# 5. Room Conflicts
room_conflicts = df_all.groupby(['Room', 'Day', 'Time']).filter(lambda x: len(x) > 1)

# 6. Room Type Validity
invalid_room_types = []
for _, row in df_all.iterrows():
    session_type = row['Session'].lower()
    actual_type = room_type_map.get(row['Room'], '')
    course_code = row['Course'].split('-')[0].strip().upper()
    section = row['Section']

    # Find matching course
    matching_course = next((c for c in expanded_courses if c['CourseCode'].strip().upper() == course_code and c['Section'] == section), None)
    lab_needs_room = matching_course.get('LabNeedsRoom', True) if matching_course else True
    required_ccl = str(matching_course.get('RequiredCCL', '0')).strip() == '1' if matching_course else False
    specific_lab = str(matching_course.get('SpecificLabRoom', '')).strip().lower() if matching_course else ''

    if session_type == 'lab':
        if not lab_needs_room:
            # Lab session with LabNeedsRoom = False → must be in a lecture room AND match SpecificLabRoom
            if actual_type != 'lecture' or (specific_lab and row['Room'].strip().lower() not in [r.strip().lower() for r in specific_lab.split(';') if r]):
                invalid_room_types.append(row)
        elif required_ccl:
            # Required CCL → must be in a lab room (enforced again below in specific room section)
            if actual_type != 'lab':
                invalid_room_types.append(row)
        else:
            # Normal lab → must be in lab room
            if actual_type != 'lab':
                invalid_room_types.append(row)
    elif session_type == 'lecture' and actual_type != 'lecture':
        invalid_room_types.append(row)

# 7. SpecificLabRoom Violations
specific_violations = []
for _, row in df_all.iterrows():
    code = row['Course'].split('-')[0].strip().upper()
    section = row['Section']
    session = row['Session'].lower()
    assigned_room = row['Room']
    for course in expanded_courses:
        if course['CourseCode'].strip().upper() == code and course['Section'] == section:
            if str(course.get('RequiredCCL')).strip() == '1' and session == 'lab':
                required_rooms = [r.strip().lower() for r in str(course.get('SpecificLabRoom', '')).split(';') if r]
                if assigned_room.strip().lower() not in required_rooms:
                    specific_violations.append(row)
            break

# === Report Summary ===
print(f"📌 FITT/NSTP Scheduling Violations: {len(fitt_nstp_violations)}")
if fitt_nstp_violations:
    print(pd.DataFrame(fitt_nstp_violations)[['Section', 'Course', 'Day']])

print(f"📌 1st/2nd-Year Regular Courses Scheduled Fri/Sat: {len(regular_day_violations)}")
if regular_day_violations:
    print(pd.DataFrame(regular_day_violations)[['Section', 'Course', 'Day']])

print(f"📌 Instructor Qualification Issues: {len(invalid_qual)}")
if not invalid_qual.empty:
    print(invalid_qual[['Instructor', 'Course', 'Section']])

print(f"📌 Instructors Over MaxLoad: {len(overloaded)}")
if overloaded:
    print(pd.DataFrame(overloaded))

print(f"📌 Instructor Time Conflicts: {len(instructor_time_conflicts)}")
if not instructor_time_conflicts.empty:
    print(instructor_time_conflicts[['Instructor', 'Day', 'Time', 'Course']])

print(f"📌 Room Conflicts (same Room, Day, Time): {len(room_conflicts)}")
if not room_conflicts.empty:
    print(room_conflicts[['Room', 'Day', 'Time', 'Course']])

print(f"📌 Invalid Room Type Assignments: {len(invalid_room_types)}")
if invalid_room_types:
    print(pd.DataFrame(invalid_room_types)[['Room', 'Session', 'Course']])

print(f"📌 Specific Lab Room Violations: {len(specific_violations)}")
if specific_violations:
    print(pd.DataFrame(specific_violations)[['Section', 'Course', 'Room', 'Session']])

