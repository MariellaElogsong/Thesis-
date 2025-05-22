# aco_optimizer.py

import pandas as pd
import random
import os
from collections import defaultdict

# === Load CSV files ===
courses_df = pd.read_csv(".venv/bin/courses.csv")
minor_df = pd.read_csv(".venv/bin/minorcourses.csv")
instructors_df = pd.read_csv(".venv/bin/instructors.csv")
rooms_df = pd.read_csv(".venv/bin/rooms.csv")

minor_courses_set = set(minor_df['CourseCode'].unique())
all_courses_df = pd.concat([courses_df, minor_df], ignore_index=True)

# === Preprocess Helper Functions ===
def parse_list(s):
    day_map = {
        "Mon": "Monday", "Tue": "Tuesday", "Wed": "Wednesday",
        "Thu": "Thursday", "Fri": "Friday", "Sat": "Saturday", "Sun": "Sunday"
    }
    return [day_map.get(x.strip(), x.strip()) for x in str(s).split(';') if x.strip()]


def get_section_year(section):
    return int(section.split()[1].split('-')[0]) if '-' in section else 1

def allowed_days_for_year(year):
    if year in [1, 3]: return ['Monday', 'Wednesday', 'Friday']
    if year in [2, 4]: return ['Tuesday', 'Thursday', 'Friday']
    return ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

def get_available_instructors(course_code, day):
    matches = []
    for _, row in instructors_df.iterrows():
        if course_code in parse_list(row['CoursesCanTeach']):
            if day in parse_list(row['AvailableDays']):
                matches.append(row['InstructorName'])
    return matches

def get_available_rooms(room_type, day):
    rooms = []
    for _, row in rooms_df.iterrows():
        if row['RoomType'] == room_type and day in parse_list(row['AvailableDays']):
            rooms.append(row['RoomID'])
    return rooms

time_blocks_cache = [f"{str(h).zfill(2)}:00-{str(h+1).zfill(2)}:00" for h in range(7, 19)]

def extract_all_required_section_courses():
    required = defaultdict(set)
    for _, row in all_courses_df.iterrows():
        for section in parse_list(row['Sections']):
            required[section].add(row['CourseCode'])
    return required

# === Ant Class ===
class Ant:
    def __init__(self):
        self.timetable = []
        self.load_tracker = defaultdict(int)
        self.section_day_tracker = defaultdict(set)
        self.instructor_day_tracker = defaultdict(lambda: defaultdict(list))
        self.section_course_tracker = defaultdict(set)
    
    
    def build_schedule_for(self, row, section):
        course_code = row['CourseCode']
        lecture_hours = int(row['LectureHours'])
        lab_hours = int(row['LabHours'])
        specific_rooms = parse_list(row['SpecificLabRoom'])
        is_lab_ccl = int(row['RequiredCCL']) == 1
        year = get_section_year(section)
        allowed_days = allowed_days_for_year(year)
        is_minor = course_code in minor_courses_set

        if not hasattr(self, 'room_usage'):
            self.room_usage = set()
        if not hasattr(self, 'section_time_tracker'):
            self.section_time_tracker = defaultdict(lambda: defaultdict(list))

        for session_type, hours in [('Lecture', lecture_hours), ('Lab', lab_hours)]:
            if hours == 0:
                continue

            assigned = False
            instructor_candidates = []
            for day in allowed_days:
                instructor_candidates += get_available_instructors(course_code, day)
            instructor_candidates = list(set(instructor_candidates))
            random.shuffle(instructor_candidates)

            for instructor in instructor_candidates:
                maxload = instructors_df.loc[instructors_df['InstructorName'] == instructor, 'MaxLoad'].values[0]
                current_load = self.load_tracker[instructor]
                if current_load + hours > maxload:
                    continue

                for day in allowed_days:
                    room_type = 'Lab' if session_type == 'Lab' else 'Lecture'
                    room_candidates = specific_rooms if is_lab_ccl and session_type == 'Lab' else get_available_rooms(room_type, day)
                    if not room_candidates:
                        continue

                    # Shuffle time blocks and rooms to prevent repetition
                    time_blocks = time_blocks_cache.copy()
                    random.shuffle(time_blocks)
                    shuffled_rooms = room_candidates.copy()
                    random.shuffle(shuffled_rooms)

                    for time_block in time_blocks:
                        for room in shuffled_rooms:
                            # Conflict checks
                            if time_block in self.instructor_day_tracker[instructor].get(day, []):
                                continue
                            if time_block in self.section_time_tracker[section].get(day, []):
                                continue
                            if (room, day, time_block) in self.room_usage:
                                continue

                            # Assign
                            self.timetable.append({
                                'Section': section,
                                'Course': course_code,
                                'Session': session_type,
                                'Room': room,
                                'Day': day,
                                'Time': time_block,
                                'Instructor': instructor
                            })

                            print(f"✅ Assigned: {section} - {course_code} ({session_type}) → {instructor} on {day} at {time_block} in {room}")

                            self.load_tracker[instructor] += hours
                            self.section_day_tracker[section].add(day)
                            self.instructor_day_tracker[instructor][day].append(time_block)
                            self.section_course_tracker[section].add(course_code)
                            self.section_time_tracker[section][day].append(time_block)
                            self.room_usage.add((room, day, time_block))
                            assigned = True
                            break
                        if assigned:
                            break
                    if assigned:
                        break
                if assigned:
                    break

            # === Fallback ===
            if not assigned:
                fallback_day = random.choice(allowed_days)
                fallback_time = random.choice(time_blocks_cache)
                room_type = 'Lab' if session_type == 'Lab' else 'Lecture'
                room_candidates = specific_rooms if is_lab_ccl and session_type == 'Lab' else get_available_rooms(room_type, fallback_day)
                room = random.choice(room_candidates) if room_candidates else "TBA"

                if not is_minor:
                    print(f"🚫 Could not assign {course_code} ({session_type}) → tried {len(instructor_candidates)} instructors with available load.")
                    print(f"⚠️  Fallback: {section} - {course_code} ({session_type}) → using 'Sample Instructor'")
                    if not instructor_candidates:
                        print(f"   ➤ No instructor teaches {course_code} on allowed days")
                    else:
                        for candidate in instructor_candidates:
                            maxload = instructors_df.loc[instructors_df['InstructorName'] == candidate, 'MaxLoad'].values[0]
                            current_load = self.load_tracker[candidate]
                            print(f"     └ {candidate}: load {current_load}/{maxload}")

                fallback_instructor = "No Assigned Instructor" if not is_minor else "Sample Instructor"

                self.timetable.append({
                    'Section': section,
                    'Course': course_code,
                    'Session': session_type,
                    'Room': room,
                    'Day': fallback_day,
                    'Time': fallback_time,
                    'Instructor': fallback_instructor
                })

                self.section_day_tracker[section].add(fallback_day)
                self.instructor_day_tracker[fallback_instructor][fallback_day].append(fallback_time)
                self.section_course_tracker[section].add(course_code)
                self.section_time_tracker[section][fallback_day].append(fallback_time)
                self.room_usage.add((room, fallback_day, fallback_time))


    def build_schedule(self):
        for _, row in all_courses_df.iterrows():
            course_code = row['CourseCode']
            lecture_hours = int(row['LectureHours'])
            lab_hours = int(row['LabHours'])
            sections = parse_list(row['Sections'])
            specific_rooms = parse_list(row['SpecificLabRoom'])
            is_lab_ccl = int(row['RequiredCCL']) == 1

            for section in sections:
                year = get_section_year(section)
                allowed_days = allowed_days_for_year(year)

                for session_type, hours in [('Lecture', lecture_hours), ('Lab', lab_hours)]:
                    if hours == 0:
                        continue

                    assigned = False
                    random.shuffle(allowed_days)
                    for day in allowed_days:
                        time_options = random.sample(time_blocks_cache, min(5, len(time_blocks_cache)))
                        for time_block in time_options:
                            instructor_candidates = get_available_instructors(course_code, day)
                            instructor = "Sample Instructor"
                            random.shuffle(instructor_candidates)
                            for candidate in instructor_candidates:
                                maxload = instructors_df.loc[instructors_df['InstructorName'] == candidate, 'MaxLoad'].values[0]
                                if self.load_tracker[candidate] + hours <= maxload:
                                    instructor = candidate
                                    self.load_tracker[candidate] += hours
                                    break


                            if instructor != "Sample Instructor" and self.load_tracker[instructor] + hours > instructors_df.loc[instructors_df['InstructorName'] == instructor, 'MaxLoad'].values[0]:
                                continue

                            room_type = 'Lab' if session_type == 'Lab' else 'Lecture'
                            room_candidates = specific_rooms if is_lab_ccl and session_type == 'Lab' else get_available_rooms(room_type, day)
                            if not room_candidates:
                                continue

                            room = random.choice(room_candidates)

                            self.timetable.append({
                                'Section': section,
                                'Course': course_code,
                                'Session': session_type,
                                'Room': room,
                                'Day': day,
                                'Time': time_block,
                                'Instructor': instructor
                            })

                            self.load_tracker[instructor] += hours
                            self.section_day_tracker[section].add(day)
                            self.instructor_day_tracker[instructor][day].append(time_block)
                            self.section_course_tracker[section].add(course_code)
                            assigned = True
                            break
                        if assigned:
                            break

# === Run ACO Optimizer (Basic Loop) ===
def run_aco(num_ants=5, iterations=20):
    os.makedirs("output_schedule_aco", exist_ok=True)
    all_year_groups = defaultdict(list)

    # === Group courses by Year Level based on Section prefix ===
    for _, row in all_courses_df.iterrows():
        for section in parse_list(row['Sections']):
            year_key = " ".join(section.strip().split()[:2])
            all_year_groups[year_key].append((row, section))

    full_timetable = []

    for year, course_section_pairs in sorted(all_year_groups.items()):
        print(f"\n📅 Optimizing timetable for {year}...")

        best_timetable = []
        best_score = float('-inf')
        required_courses = defaultdict(set)
        for row, section in course_section_pairs:
            required_courses[section].add(row['CourseCode'])

        for i in range(iterations):
            ants = [Ant() for _ in range(num_ants)]
            for ant in ants:
                for row, section in course_section_pairs:
                    ant.build_schedule_for(row, section)
                score = evaluate_fitness(ant.timetable, ant.section_course_tracker, required_courses)
                if score > best_score:
                    best_score = score
                    best_timetable = ant.timetable
            print(f"  Iteration {i+1}/{iterations} for {year} → Best Score: {best_score:.2f}")

        # Save result
        df = pd.DataFrame(best_timetable)
        df.to_csv(f"output_schedule_aco/timetable_{year.replace(' ', '_')}.csv", index=False)
        full_timetable.extend(best_timetable)

    # Final output
    df_all = pd.DataFrame(full_timetable)
    df_all.to_csv("final_timetable_aco.csv", index=False)
    print("\n✅ All year-level timetables saved to 'final_timetable_aco.csv'")

    # Attempt to import and run aco_checker.py
    try:
        import aco_checker  # Ensure aco_checker is present in your environment
        aco_checker.main()  # Run the main function of aco_checker
    except ImportError:
        print("⚠️ Warning: aco_checker.py not found or could not be imported.")
    except Exception as e:
        print(f"⚠️ Error running aco_checker.py: {e}")

# === Fitness Evaluation Function (Expanded) ===
def evaluate_fitness(timetable, section_course_tracker, required_courses):
    score = 0
    instructor_load = defaultdict(int)
    section_days = defaultdict(set)
    section_time_spans = defaultdict(lambda: defaultdict(list))
    instructor_idle = defaultdict(lambda: defaultdict(list))
    sample_instructor_penalty = 0
    missing_course_penalty = 0

    course_instructors = defaultdict(set)
    section_sessions = defaultdict(lambda: defaultdict(list))  # section[day] = [(time, session_type)]
    room_usage_per_day = defaultdict(lambda: defaultdict(int))  # room[day] = count

    for entry in timetable:
        instr = entry['Instructor']
        section = entry['Section']
        day = entry['Day']
        course = entry['Course']
        session = entry['Session']
        room = entry['Room']
        hrs = 1
        start_hr = int(entry['Time'].split(':')[0])

        instructor_load[instr] += hrs
        section_days[section].add(day)
        section_time_spans[section][day].append(start_hr)
        instructor_idle[instr][day].append(start_hr)
        course_instructors[course].add(instr)
        section_sessions[section][day].append((start_hr, session))
        room_usage_per_day[room][day] += 1

        if instr == "Sample Instructor" and entry['Course'] not in minor_courses_set:
            sample_instructor_penalty += 1

    # === Original Constraints ===

    for sec, days in section_days.items():
        score += 5 if len(days) == 3 else -3 * abs(3 - len(days))

    score -= 10 * sample_instructor_penalty

    loads = [v for k, v in instructor_load.items() if k != "Sample Instructor"]
    if loads:
        avg = sum(loads) / len(loads)
        score -= sum(abs(l - avg) for l in loads)

    for section, required in required_courses.items():
        scheduled = section_course_tracker.get(section, set())
        missing = required - scheduled
        missing_course_penalty += len(missing)
    score -= 15 * missing_course_penalty

    for section, day_map in section_time_spans.items():
        for day, hours in day_map.items():
            if len(hours) > 1:
                spread = max(hours) - min(hours) + 1
                idle = spread - len(hours)
                score -= idle

    for instr, day_map in instructor_idle.items():
        for day, hours in day_map.items():
            if len(hours) > 1:
                spread = max(hours) - min(hours) + 1
                idle = spread - len(hours)
                score -= 0.5 * idle

    # === New Constraints ===

    # 7. Efficient Room Usage
    for room, day_map in room_usage_per_day.items():
        for day, count in day_map.items():
            if count == 1:
                score -= 2
            elif count >= 3:
                score += 1

    # 8. 1-hour breaks between section classes
    for section, day_sessions in section_sessions.items():
        for day, items in day_sessions.items():
            times = sorted(t for t, _ in items)
            for i in range(1, len(times)):
                if times[i] - times[i - 1] == 1:
                    score -= 1  # penalize no break between classes

    # 9. No back-to-back labs
    for section, day_sessions in section_sessions.items():
        for day, items in day_sessions.items():
            sorted_sessions = sorted(items)
            for i in range(1, len(sorted_sessions)):
                prev_hr, prev_type = sorted_sessions[i - 1]
                curr_hr, curr_type = sorted_sessions[i]
                if curr_hr - prev_hr == 1 and prev_type == "Lab" and curr_type == "Lab":
                    score -= 2  # penalize back-to-back labs

    # 10. Same instructor per course (across sections)
    for course, instructors in course_instructors.items():
        if len(instructors - {"Sample Instructor"}) > 1:
            score -= 5 * (len(instructors) - 1)

    return score

if __name__ == "__main__":
    run_aco(num_ants=2, iterations=3)  # Lower numbers for testing

