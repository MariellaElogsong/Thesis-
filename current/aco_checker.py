# aco_checker.py

import pandas as pd
from collections import defaultdict

def parse_list(s):
    return [x.strip() for x in str(s).split(';') if x.strip()]

def parse_time_range(time_str):
    try:
        start, end = time_str.split('-')
        return int(start.split(':')[0]), int(end.split(':')[0])
    except:
        return 7, 17

def main():
    df = pd.read_csv('final_timetable_aco.csv')
    if df.empty:
        print("❌ Timetable is empty.")
        return

    instructor_load = defaultdict(int)
    section_days = defaultdict(set)
    section_times = defaultdict(lambda: defaultdict(list))
    instructor_idle = defaultdict(lambda: defaultdict(list))
    sample_instructor_penalty = 0
    no_assigned_fallback = 0
    course_instructors = defaultdict(set)
    section_sessions = defaultdict(lambda: defaultdict(list))
    room_usage = defaultdict(lambda: defaultdict(int))
    section_course_tracker = defaultdict(set)
    required_courses = defaultdict(set)

    for _, row in df.iterrows():
        sec = row['Section']
        instr = row['Instructor']
        day = row['Day']
        course = row['Course']
        course_code = row['Course']  # ✅ Use course name instead
        sess = row['Session']
        room = row['Room']
        time = row['Time']
        start_hr = int(time.split(':')[0])

        # 1. Sample Instructor
        if instr == "Sample Instructor":
            sample_instructor_penalty += 1
        elif instr == "No Assigned":
            no_assigned_fallback += 1

        # 2. Instructor load
        instructor_load[instr] += 1

        # 3. Section 3-day
        section_days[sec].add(day)

        # 4. Compactness
        section_times[sec][day].append(start_hr)

        # 5. Instructor idle
        instructor_idle[instr][day].append(start_hr)

        # 6. Course-Instructor consistency
        course_instructors[course].add(instr)

        # 7. Back-to-back lab
        section_sessions[sec][day].append((start_hr, sess))

        # 8. 1-hr break check
        section_sessions[sec][day].sort()

        # 9. Room usage
        room_usage[room][day] += 1

        # ✅ Correct tracker
        section_course_tracker[sec].add(course_code)

    print("\n🔎 Soft Constraint Violations Summary:")
    score = 0

    # 1. 3-day schedule
    day_violations = 0
    for sec, days in section_days.items():
        delta = abs(3 - len(days))
        if delta != 0:
            day_violations += 1
            score -= 3 * delta
        else:
            score += 5
    print(f"❌ 3-day section schedule: {day_violations} violations")

    # 2. Instructor load balance
    instr_values = [v for k, v in instructor_load.items() if k != "Sample Instructor"]
    if instr_values:
        avg = sum(instr_values) / len(instr_values)
        imbalance = sum(abs(v - avg) for v in instr_values)
        score -= imbalance
        print(f"❌ Instructor load imbalance: total imbalance {imbalance:.2f}")

    # 3. Sample instructor
    score -= 10 * sample_instructor_penalty
    print(f"❌ Sample Instructor use: {sample_instructor_penalty} times")

   # 3.5. No Assigned fallback (major)
    no_assigned_fallback = sum(
        count for name, count in instructor_load.items()
        if name.strip().lower() == "no assigned instructor"
    )
    score -= 10 * no_assigned_fallback
    print(f"❌ No Assigned Instructor (major fallback): {no_assigned_fallback} times")




    # 4. Compact daily hours (per section)
    compact_violations = 0
    for sec, day_map in section_times.items():
        for day, hours in day_map.items():
            if len(hours) > 1:
                spread = max(hours) - min(hours) + 1
                idle = spread - len(hours)
                score -= idle
                compact_violations += idle
    print(f"❌ Idle gaps in daily section schedules: -{compact_violations} points")

    # 5. Instructor idle time
    idle_penalty = 0
    for instr, days in instructor_idle.items():
        for d, times in days.items():
            if len(times) > 1:
                spread = max(times) - min(times) + 1
                idle = spread - len(times)
                idle_penalty += idle * 0.5
    score -= idle_penalty
    print(f"❌ Instructor idle time: -{idle_penalty:.2f} points")

    # 6. Same instructor per course
    inconsistent = 0
    for course, instructors in course_instructors.items():
        unique = instructors - {"Sample Instructor"}
        if len(unique) > 1:
            inconsistent += len(unique) - 1
            score -= 5 * (len(unique) - 1)
    print(f"❌ Multiple instructors per course: {inconsistent} violations")

    # 7. Back-to-back lab
    back2back_violations = 0
    for sec, day_map in section_sessions.items():
        for day, sessions in day_map.items():
            for i in range(1, len(sessions)):
                prev_hr, prev_type = sessions[i - 1]
                curr_hr, curr_type = sessions[i]
                if curr_type == "Lab" and prev_type == "Lab" and curr_hr - prev_hr == 1:
                    score -= 2
                    back2back_violations += 1
    print(f"❌ Back-to-back lab sessions: {back2back_violations} violations")

    # 8. No 1-hr break
    no_breaks = 0
    for sec, day_map in section_sessions.items():
        for day, sessions in day_map.items():
            hours = sorted([t for t, _ in sessions])
            for i in range(1, len(hours)):
                if hours[i] - hours[i-1] == 1:
                    score -= 1
                    no_breaks += 1
    print(f"❌ No 1-hour break between classes: {no_breaks} instances")

    # 9. Room usage efficiency
    room_penalty = 0
    room_bonus = 0
    for room, day_map in room_usage.items():
        for day, count in day_map.items():
            if count == 1:
                score -= 2
                room_penalty += 1
            elif count >= 3:
                score += 1
                room_bonus += 1
    print(f"❌ Inefficient room use (1/day): {room_penalty}  |  ✅ Bonus (3+/day): {room_bonus}")

    # 10. Required course check
    missing = 0
    all_courses_df = pd.concat([
        pd.read_csv('.venv/bin/courses.csv'),
        pd.read_csv('.venv/bin/minorcourses.csv')
    ], ignore_index=True)

    for _, row in all_courses_df.iterrows():
        for sec in parse_list(row['Sections']):
            required_courses[sec].add(row['CourseCode'])

    for sec, required in required_courses.items():
        scheduled = section_course_tracker.get(sec, set())
        diff = required - scheduled
        if diff:
            score -= 15 * len(diff)
            missing += len(diff)
    print(f"❌ Missing required courses: {missing} total")

    print(f"\n🎯 Final Calculated Fitness Score: {score:.2f}\n")

if __name__ == "__main__":
    main()

