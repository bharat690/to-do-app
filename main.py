"""
==================================================
✅ Smart To-Do App with Calendar, Goals & WhatsApp
==================================================

Authors   : Bharat Rai , Ayush Kumar Sahani & Ayushmaan Kaithwar 
Course    : Logic Building with Python (End Sem Project)  
Stack     : Streamlit + MySQL + Twilio + Plotly + Pandas  
Date      : 22 April 2025

📌 Description:
This is a full-featured task management and productivity tracker app.
It runs on Streamlit and connects to a MySQL backend. Includes:
- Recurring tasks (daily, weekly, monthly)
- Calendar and heatmap views
- Goal tracker with streak logic
- WhatsApp notifications (via Twilio API)
- Gamification, quotes, and dashboard stats

--------------------------------------------------

🔧 Setup Instructions:

1. ✅ Ensure you have Python 3.9+ and pip installed.
2. ✅ Install dependencies:
    pip install -r requirements.txt

3. ✅ Create the MySQL database:
    CREATE DATABASE todo_app;

4. ✅ Update database credentials in the `get_db_connection()` function:
    host="localhost",
    user="root",
    password="YOUR_MYSQL_PASSWORD",
    database="todo_app"

5. ✅ Enable Twilio WhatsApp notifications:
    - Get a Twilio trial account
    - Replace `twilio_sid`, `twilio_auth_token`, and numbers in `secrets.toml`

6. ✅ Run the app:
    streamlit run main.py

--------------------------------------------------

📦 Notes:
- All core logic is self-contained in this file (no external modules).
- Designed to be deployed easily on Streamlit Cloud or localhost.
- Goal tracking resets automatically weekly/monthly.
- All tasks are auto-reloaded with `st.rerun()` after updates.

Enjoy building your productivity superpower 💪

"""







import streamlit as st
import mysql.connector
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.graph_objects as go
from apscheduler.schedulers.background import BackgroundScheduler
import random
from twilio.rest import Client
import os



# ----------------- DB CONNECTION -----------------
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="PASSWORD",
        database="todo_app"
    )

# ----------------- DB SETUP -----------------
def create_table():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INT AUTO_INCREMENT PRIMARY KEY,
            title VARCHAR(255),
            description TEXT,
            status ENUM('Pending','Completed') DEFAULT 'Pending',
            priority ENUM('Low','Medium','High') DEFAULT 'Medium',
            task_type ENUM('One-time','Daily','Weekly','Monthly') DEFAULT 'One-time',
            week_days VARCHAR(50),
            monthly_date INT,
            end_date DATE,
            last_completed DATE,
            completed_at DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Create goal tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            period ENUM('Weekly','Monthly') DEFAULT 'Weekly',
            target_count INT,
            start_date DATE,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Create notification settings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notification_settings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_phone VARCHAR(20),
            send_daily BOOLEAN DEFAULT TRUE,
            daily_time TIME DEFAULT '08:00:00',
            send_evening BOOLEAN DEFAULT TRUE,
            evening_time TIME DEFAULT '19:00:00',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
    ''')
    
    conn.commit()
    conn.close()

# ----------------- CRUD OPERATIONS -----------------
def add_task(title, desc, priority, task_type, week_days, monthly_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO tasks 
          (title, description, priority, task_type, week_days, monthly_date, end_date, last_completed)
        VALUES (%s,%s,%s,%s,%s,%s,%s,NULL);
    ''', (title, desc, priority, task_type, week_days, monthly_date, end_date))
    conn.commit()
    conn.close()


def get_tasks():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM tasks ORDER BY created_at DESC;')
    tasks = cursor.fetchall()
    conn.close()
    return tasks


def update_task_status(task_id, new_status, last_completed=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if last_completed:
        cursor.execute(
            'UPDATE tasks SET status=%s, last_completed=%s, completed_at=%s WHERE id=%s;', 
            (new_status, last_completed, last_completed, task_id)
        )
    else:
        cursor.execute(
            'UPDATE tasks SET status=%s WHERE id=%s;', 
            (new_status, task_id)
        )
    conn.commit()
    conn.close()


def delete_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM tasks WHERE id=%s;', (task_id,))
    conn.commit()
    conn.close()


def edit_task(task_id, title, desc, priority, task_type, week_days, monthly_date, end_date):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE tasks
        SET title=%s, description=%s, priority=%s,
            task_type=%s, week_days=%s, monthly_date=%s, end_date=%s
        WHERE id=%s;
    ''', (title, desc, priority, task_type, week_days, monthly_date, end_date, task_id))
    conn.commit()
    conn.close()

# ----------------- GOAL TRACKING -----------------
def save_goal(period, target_count):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = date.today()
    if period == "Weekly":
        # Calculate start of week (Monday) and end of week (Sunday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    else:  # Monthly
        # First and last day of current month
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    # Check if goal for current period exists
    cursor.execute(
        'SELECT id FROM goals WHERE period=%s AND start_date=%s AND end_date=%s',
        (period, start_date, end_date)
    )
    existing = cursor.fetchone()
    
    if existing:
        # Update existing goal
        cursor.execute(
            'UPDATE goals SET target_count=%s WHERE id=%s',
            (target_count, existing[0])
        )
    else:
        # Create new goal
        cursor.execute(
            'INSERT INTO goals (period, target_count, start_date, end_date) VALUES (%s, %s, %s, %s)',
            (period, target_count, start_date, end_date)
        )
    
    conn.commit()
    conn.close()

def get_current_goal(period):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    today = date.today()
    if period == "Weekly":
        # Calculate start of week (Monday) and end of week (Sunday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    else:  # Monthly
        # First and last day of current month
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    cursor.execute(
        'SELECT * FROM goals WHERE period=%s AND start_date=%s AND end_date=%s',
        (period, start_date, end_date)
    )
    goal = cursor.fetchone()
    conn.close()
    
    return goal

def get_completed_count(period):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    today = date.today()
    if period == "Weekly":
        # Calculate start of week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    else:  # Monthly
        # First day of current month
        start_date = date(today.year, today.month, 1)
        if today.month == 12:
            end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
    
    cursor.execute(
        'SELECT COUNT(*) FROM tasks WHERE status="Completed" AND completed_at BETWEEN %s AND %s',
        (start_date, end_date)
    )
    count = cursor.fetchone()[0]
    conn.close()
    
    return count

# ----------------- NOTIFICATION SETTINGS CRUD -----------------
def get_notification_settings():
    """Get current notification settings from database."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Try to get existing settings
    cursor.execute('SELECT * FROM notification_settings LIMIT 1')
    settings = cursor.fetchone()
    
    # If no settings exist, create default settings
    if not settings:
        cursor.execute('''
            INSERT INTO notification_settings 
            (user_phone, send_daily, daily_time, send_evening, evening_time)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            os.environ.get('USER_PHONE_NUMBER', ''),
            True,
            '08:00:00',
            True,
            '19:00:00'
        ))
        conn.commit()
        
        # Fetch the newly created settings
        cursor.execute('SELECT * FROM notification_settings LIMIT 1')
        settings = cursor.fetchone()
    
    conn.close()
    return settings

def save_notification_settings(user_phone, send_daily, daily_time, send_evening, evening_time):
    """Save notification settings to database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if settings already exist
    cursor.execute('SELECT id FROM notification_settings LIMIT 1')
    existing = cursor.fetchone()
    
    if existing:
        # Update existing settings
        cursor.execute('''
            UPDATE notification_settings
            SET user_phone=%s, send_daily=%s, daily_time=%s, 
                send_evening=%s, evening_time=%s
            WHERE id=%s
        ''', (
            user_phone, send_daily, daily_time, 
            send_evening, evening_time, existing[0]
        ))
    else:
        # Create new settings
        cursor.execute('''
            INSERT INTO notification_settings 
            (user_phone, send_daily, daily_time, send_evening, evening_time)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_phone, send_daily, daily_time, 
            send_evening, evening_time
        ))
    
    conn.commit()
    conn.close()
    
    # Also update environment variable
    os.environ['USER_PHONE_NUMBER'] = user_phone
    
    return True

# ----------------- TWILIO SETUP -----------------
def get_twilio_client():
    """Get authenticated Twilio client using environment variables."""
    account_sid = os.environ.get('TWILIO_ACCOUNT_SID')
    auth_token = os.environ.get('TWILIO_AUTH_TOKEN')
    
    if not account_sid or not auth_token:
        # For development/demo, you could use these values directly
        # But for production, use environment variables
        account_sid = "ACC_SID"  # Replace with your Twilio Account SID
        auth_token = "AUTH_TOKEN"    # Replace with your Twilio Auth Token
    
    return Client(account_sid, auth_token)

def send_sms(body_text):
    """Send SMS notification using Twilio."""
    try:
        client = get_twilio_client()
        
        # Get phone numbers from environment variables or use defaults
        from_number = os.environ.get('TWILIO_PHONE_NUMBER', '+12345678')  # Replace with your Twilio number
        to_number = os.environ.get('USER_PHONE_NUMBER', '+12345678')      # Replace with recipient number
        
        # Basic validation for E.164 format
        if not to_number.startswith('+') or not to_number[1:].isdigit():
            return False, "Invalid phone number format. Must start with + followed by country code and number (no spaces or special characters)."
        
        message = client.messages.create(
            body=body_text,
            from_=from_number,
            to=to_number
        )
        
        return True, message.sid
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return False, str(e)

# ----------------- NOTIFICATION FUNCTIONS -----------------
def send_task_reminder(task_id):
    """Send a reminder for a specific task."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
    task = cursor.fetchone()
    conn.close()
    
    if not task:
        return False, "Task not found"
    
    # Create message body
    message_body = f"REMINDER: {task['title']}\n"
    message_body += f"Priority: {task['priority']}\n"
    
    if task['description']:
        message_body += f"Details: {task['description'][:100]}"
        if len(task['description']) > 100:
            message_body += "..."
    
    # Send the message
    return send_sms(message_body)

def send_daily_summary():
    """Send a summary of today's tasks."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    today = date.today()
    
    # Get all tasks due today
    tasks_today = []
    
    # One-time tasks due today
    cursor.execute('SELECT * FROM tasks WHERE task_type = "One-time" AND end_date = %s', (today,))
    one_time_tasks = cursor.fetchall()
    tasks_today.extend(one_time_tasks)
    
    # Daily tasks
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Daily"')
    daily_tasks = cursor.fetchall()
    tasks_today.extend(daily_tasks)
    
    # Weekly tasks for today's weekday
    day_name = today.strftime("%A")
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Weekly"')
    weekly_tasks = cursor.fetchall()
    for task in weekly_tasks:
        if task['week_days'] and day_name in task['week_days'].split(','):
            tasks_today.append(task)
    
    # Monthly tasks for today's day of month
    day_of_month = today.day
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Monthly" AND monthly_date = %s', (day_of_month,))
    monthly_tasks = cursor.fetchall()
    tasks_today.extend(monthly_tasks)
    
    conn.close()
    
    # If no tasks, send a different message
    if not tasks_today:
        return send_sms(f"Good morning! You have no tasks scheduled for today ({today.strftime('%A, %B %d')}).")
    
    # Create the summary message
    pending_tasks = [t for t in tasks_today if t['status'] == 'Pending']
    completed_tasks = [t for t in tasks_today if t['status'] == 'Completed']
    
    message_body = f"Daily Summary for {today.strftime('%A, %B %d')}:\n\n"
    
    # Pending tasks
    message_body += f"📝 PENDING: {len(pending_tasks)} tasks\n"
    for i, task in enumerate(pending_tasks, 1):
        if i <= 5:  # Limit to first 5 tasks to avoid very long messages
            message_body += f"{i}. {task['title']} ({task['priority']})\n"
        elif i == 6:
            message_body += f"...and {len(pending_tasks) - 5} more\n"
            break
    
    # Completed tasks
    message_body += f"\n✓ COMPLETED: {len(completed_tasks)} tasks\n"
    
    # Add a motivational message
    if len(pending_tasks) > 0:
        message_body += "\n" + generate_motivation_quote()
    
    # Send the message
    return send_sms(message_body)

def send_evening_reminder():
    """Send a reminder in the evening if tasks are still pending."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    today = date.today()
    
    # Get pending tasks due today (similar logic to daily summary)
    pending_today = []
    
    # One-time tasks due today
    cursor.execute('SELECT * FROM tasks WHERE task_type = "One-time" AND end_date = %s AND status = "Pending"', (today,))
    one_time_tasks = cursor.fetchall()
    pending_today.extend(one_time_tasks)
    
    # Daily tasks
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Daily" AND status = "Pending"')
    daily_tasks = cursor.fetchall()
    pending_today.extend(daily_tasks)
    
    # Weekly tasks for today's weekday
    day_name = today.strftime("%A")
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Weekly" AND status = "Pending"')
    weekly_tasks = cursor.fetchall()
    for task in weekly_tasks:
        if task['week_days'] and day_name in task['week_days'].split(','):
            pending_today.append(task)
    
    # Monthly tasks for today's day of month
    day_of_month = today.day
    cursor.execute('SELECT * FROM tasks WHERE task_type = "Monthly" AND monthly_date = %s AND status = "Pending"', (day_of_month,))
    monthly_tasks = cursor.fetchall()
    pending_today.extend(monthly_tasks)
    
    conn.close()
    
    # If no pending tasks, no need to send a reminder
    if not pending_today:
        return True, "No pending tasks"
    
    # Create the reminder message
    message_body = f"Evening Reminder: You have {len(pending_today)} pending tasks for today:\n\n"
    
    for i, task in enumerate(pending_today, 1):
        if i <= 5:  # Limit to first 5 tasks
            message_body += f"{i}. {task['title']} ({task['priority']})\n"
        elif i == 6:
            message_body += f"...and {len(pending_today) - 5} more\n"
            break
    
    message_body += "\n" + generate_motivation_quote()
    
    # Send the message
    return send_sms(message_body)


# ----------------- NOTIFICATION SETTINGS UI -----------------
def notification_settings():
    """UI for notification settings."""
    st.header("📱 Notification Settings")
    
    # Phone number settings
    user_phone = '+123456789'  # Default phone number for demo purposes
    
    col1, col2 = st.columns(2)
    
    with col1:
        send_daily = st.checkbox("Daily Morning Summary", value=True)
        # Use a time input directly instead of strftime/strptime conversion
        daily_time = st.time_input("Time", datetime.strptime("08:00", "%H:%M").time())
    
    with col2:
        send_evening = st.checkbox("Evening Reminders", value=True)
        # Use a time input directly instead of strftime/strptime conversion
        evening_time = st.time_input("Time", datetime.strptime("19:00", "%H:%M").time())
    
    # Test notification button
    if st.button("Send Test Notification"):
        result, msg = send_sms("This is a test notification from your To-Do App!")
        if result:
            st.success("Test notification sent successfully!")
        else:
            st.error(f"Failed to send notification: {msg}")
    
    # Save settings button
    if st.button("Save Notification Settings"):
        # In a real app, you would save these to a database
        # For now, we'll just update environment variables
        os.environ['USER_PHONE_NUMBER'] = user_phone
        
        # Normally you would configure the scheduler with these times
        st.success("Notification settings saved!")


# ----------------- VISUALIZATION -----------------
def create_calendar_view(tasks):
    """
    Create a simplified calendar view of tasks using native Streamlit components.
    """
    # Filter tasks that have end dates and are not completed
    active_tasks = [t for t in tasks if t['end_date'] is not None]
    
    if not active_tasks:
        st.info("No tasks with due dates to display.")
        return
    
    # Get date range (today and next 14 days)
    today = date.today()
    date_range = [today + timedelta(days=x) for x in range(15)]
    
    # Create a dictionary of tasks by date
    tasks_by_date = {d: [] for d in date_range}
    
    for t in active_tasks:
        # For one-time tasks
        if t['task_type'] == 'One-time':
            if t['end_date'] in tasks_by_date:
                tasks_by_date[t['end_date']].append(t)
        
        # For recurring tasks
        elif t['task_type'] == 'Daily':
            # Add to all dates
            for d in date_range:
                tasks_by_date[d].append(t)
        
        elif t['task_type'] == 'Weekly':
            # Check if day of week matches
            if t['week_days']:
                weekdays = t['week_days'].split(',')
                for d in date_range:
                    day_name = d.strftime("%A")
                    if day_name in weekdays:
                        tasks_by_date[d].append(t)
        
        elif t['task_type'] == 'Monthly':
            # Check if day of month matches
            if t['monthly_date']:
                for d in date_range:
                    if d.day == t['monthly_date']:
                        tasks_by_date[d].append(t)
    
    # Display calendar
    st.write("### 📅 Next 15 Days")
    
    # Display week by week
    weeks = [date_range[i:i+7] for i in range(0, len(date_range), 7)]
    
    for week_num, week in enumerate(weeks):
        st.write(f"#### Week {week_num + 1}")
        
        cols = st.columns(len(week))
        
        for i, d in enumerate(week):
            with cols[i]:
                # Display date header
                day_name = d.strftime("%a")
                date_str = d.strftime("%d")
                
                if d == today:
                    st.markdown(f"**{day_name} {date_str} (Today)**")
                else:
                    st.write(f"{day_name} {date_str}")
                
                # Display tasks for this date
                day_tasks = tasks_by_date[d]
                
                if not day_tasks:
                    st.write("*No tasks*")
                else:
                    for t in day_tasks:
                        # Color based on priority
                        if t['priority'] == 'High':
                            color = "red"
                        elif t['priority'] == 'Medium':
                            color = "orange"
                        else:
                            color = "blue"
                        
                        # Show task with status indicator
                        status_icon = "✅" if t['status'] == 'Completed' else "⏳"
                        st.markdown(
                            f"<div style='border-left: 3px solid {color}; padding-left: 5px; margin-bottom: 5px;'>"
                            f"{status_icon} {t['title']}</div>", 
                            unsafe_allow_html=True
                        )

def create_completion_heatmap(tasks):
    """Create a heatmap visualization of task completion patterns."""
    df = pd.DataFrame(tasks)
    
    # Check if we have completed tasks with dates
    if 'completed_at' not in df.columns or df.empty or df[df['status'] == 'Completed'].empty:
        st.info("Not enough completed tasks to show trends.")
        return
    
    df['completed_at'] = pd.to_datetime(df['completed_at'])
    df = df[df['status'] == 'Completed']

    # Task count per day
    task_counts = df.groupby(df['completed_at'].dt.date).size().reset_index(name='count')

    # Create 90-day range
    start_date = date.today() - timedelta(days=90)
    end_date = date.today()
    all_dates = pd.date_range(start=start_date, end=end_date)

    heat_df = pd.DataFrame({'date': all_dates})
    heat_df['count'] = heat_df['date'].dt.date.map(
        lambda d: task_counts[task_counts['completed_at'] == d]['count'].sum() 
        if d in task_counts['completed_at'].values else 0
    )
    heat_df['dow'] = heat_df['date'].dt.weekday
    heat_df['week'] = heat_df['date'].dt.strftime('%U')

    # Format grid
    heatmap_data = heat_df.pivot(index='dow', columns='week', values='count').fillna(0)

    fig = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns,
        y=['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        colorscale = [
            [0.0, '#0f172a'],   # Deep slate
            [0.25, '#1e293b'],  # Slate dark
            [0.5, '#3b82f6'],   # Blue-500
            [0.75, '#60a5fa'],  # Blue-400
            [1.0, '#93c5fd'],   # Blue-300
        ],
        showscale=False,
        hoverongaps=False,
        xgap=3,  # uniform spacing
        ygap=3
    ))

    fig.update_layout(
        title='🧊 Task Completion Heatmap',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=280,
        margin=dict(l=20, r=20, t=40, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)


# ----------------- DASHBOARD -----------------
def task_stats(tasks):
    today = date.today()
    pending = sum(t['status']=='Pending' for t in tasks)
    completed = sum(t['status']=='Completed' for t in tasks)
    overdue = 0
    for t in tasks:
        if t['status']!='Pending':
            continue
        if t['task_type']=='One-time':
            if t['end_date'] and t['end_date'] < today:
                overdue += 1
        else:
            if not t['last_completed'] or t['last_completed'] < today:
                overdue += 1

    st.metric("✅ Completed", completed)
    st.metric("🕒 Pending", pending)
    st.metric("⚠️ Overdue", overdue)

# ----------------- NOTIFICATIONS -----------------
def generate_motivation_quote():
    quotes = [
        "Small progress is still progress!",
        "Your future self will thank you for what you do today.",
        "The secret of getting ahead is getting started.",
        "Focus on progress, not perfection.",
        "Each task completed is a step forward.",
        "Discipline is choosing between what you want now and what you want most.",
        "The only way to do great work is to love what you do.",
        "Your productivity determines your impact.",
        "The best way to predict the future is to create it.",
        "Success is the sum of small efforts repeated day in and day out."
    ]
    return random.choice(quotes)

# ----------------- SCHEDULER SETUP -----------------
# This would be in your main app startup outside of Streamlit
def setup_scheduler():
    """Set up the scheduler for automated notifications."""
    settings = get_notification_settings()
    if not settings:
        return False
    
    try:
        scheduler = BackgroundScheduler()
        
        # Add jobs if enabled
        if settings['send_daily']:
            daily_time = settings['daily_time']
            scheduler.add_job(
                send_daily_summary, 
                'cron', 
                hour=daily_time.hour, 
                minute=daily_time.minute
            )
        
        if settings['send_evening']:
            evening_time = settings['evening_time']
            scheduler.add_job(
                send_evening_reminder, 
                'cron', 
                hour=evening_time.hour, 
                minute=evening_time.minute
            )
        
        scheduler.start()
        return True
    except Exception as e:
        print(f"Error setting up scheduler: {e}")
        return False

# ----------------- MAIN APP -----------------
def main():
    st.set_page_config(page_title="To-Do App", layout="wide", page_icon="📝")
    st.title("📝 Enhanced To-Do App")

    # Initialize database tables
    create_table()

    # Initialize session state variables
    if 'editing' not in st.session_state:
        st.session_state.editing = {}
    
    if 'view' not in st.session_state:
        st.session_state.view = "List"
    
    if 'filter_status' not in st.session_state:
        st.session_state.filter_status = "All"
    
    tasks = get_tasks()

    # Sidebar: Add Task
    with st.sidebar:
        st.header("Add New Task")
        title = st.text_input("Title")
        desc = st.text_area("Description")
        priority = st.selectbox("Priority", ["Low", "Medium", "High"])
        task_type = st.selectbox("Task Type", ["One-time", "Daily", "Weekly", "Monthly"], key="add_type")

        week_days = ""
        monthly_date = None
        end_date = None

        if task_type == "Weekly":
            days = st.multiselect(
                "Select Days", 
                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                key="add_week"
            )
            week_days = ",".join(days)
        elif task_type == "Monthly":
            monthly_date = st.number_input(
                "Day of Month", min_value=1, max_value=31, step=1,
                key="add_month"
            )
        elif task_type == "One-time":
            end_date = st.date_input("End Date", min_value=date.today(), key="add_end")

        if st.button("Add Task", use_container_width=True):
            if title.strip():
                add_task(title, desc, priority, task_type, week_days, monthly_date, end_date)
                st.success("Task added!")
                st.rerun()
            else:
                st.error("Title is required")
        
        # Goal Tracker Widget
        st.header("🎯 Goal Tracker")
        goal_period = st.selectbox("Goal Period", ["Weekly", "Monthly"], key="goal_period")
        
        # Get current goal if exists
        current_goal = get_current_goal(goal_period)
        default_target = current_goal['target_count'] if current_goal else 5
        
        target_count = st.number_input(
            f"Target {goal_period} Tasks", 
            min_value=1, 
            max_value=100,
            value=default_target
        )
        
        if st.button("Set Goal", use_container_width=True):
            save_goal(goal_period, target_count)
            st.success(f"{goal_period} goal set!")
            st.rerun()
        
        # Display goal progress
        completed_count = get_completed_count(goal_period)
        
        if current_goal:
            progress = min(completed_count / current_goal['target_count'], 1.0)
            st.write(f"*Progress:* {completed_count} of {current_goal['target_count']} tasks")
            st.progress(progress)
            
            if progress >= 1.0:
                st.success("🎉 Goal achieved! Great job!")
            elif progress >= 0.5:
                st.info("👍 You're making good progress!")
            else:
                st.write(generate_motivation_quote())
        else:
            st.write("No goal set for this period yet.")

        # Add notification section to sidebar
        st.markdown("---")
        if st.button("📱 Notification Settings", use_container_width=True):
            st.session_state.view = "Notifications"
            st.rerun()

    # Add a new view for notifications
    if st.session_state.view == "Notifications":
        notification_settings()
        if st.button("Back to Tasks"):
            st.session_state.view = "List"
            st.rerun()
    else:
        # Dashboard always visible
        st.subheader("📊 Dashboard")
        stats_col1, stats_col2, stats_col3 = st.columns(3)
        with stats_col1:
            task_stats(tasks)
        
        with stats_col2:
            # Completion stats by priority
            priority_counts = {"High": 0, "Medium": 0, "Low": 0}
            for t in tasks:
                if t['status'] == 'Completed':
                    priority_counts[t['priority']] += 1
                    
            fig = go.Figure(data=[
                go.Bar(
                    x=list(priority_counts.keys()),
                    y=list(priority_counts.values()),
                    marker_color=['#ef4444', '#f97316', '#3b82f6']
                )
            ])
            fig.update_layout(
                title='Tasks by Priority',
                xaxis_title='Priority',
                yaxis_title='Completed Tasks',
                height=200,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
            
        with stats_col3:
            # Current week tasks
            today = date.today()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            
            week_tasks = [t for t in tasks if 
                          (t['task_type'] == 'One-time' and 
                           t['end_date'] and 
                           start_of_week <= t['end_date'] <= end_of_week) or
                          t['task_type'] in ['Daily', 'Weekly', 'Monthly']]
            
            completed = sum(1 for t in week_tasks if t['status'] == 'Completed')
            total = len(week_tasks)
            
            st.metric("This Week", f"{completed}/{total}")
            if total > 0:
                st.progress(completed/total)

        # View selector
        view_options = ["List", "Calendar", "Trends"]
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            selected_view = st.radio("View:", view_options, horizontal=True, key="view_selector", index=view_options.index(st.session_state.view) if st.session_state.view in view_options else 0)
            st.session_state.view = selected_view

        # Different views based on selection
        if st.session_state.view == "Calendar":
            st.subheader("📅 Calendar View")
            create_calendar_view(tasks)
        
        elif st.session_state.view == "Trends":
            st.subheader("🔥 Completion Trends")
            create_completion_heatmap(tasks)
        
        else:  # List View (default)
            st.subheader("📋 All Tasks")
            
            # Search and filter
            col1, col2 = st.columns([3, 1])
            with col1:
                search = st.text_input("Search by title", key="search")
            with col2:
                status_filter = st.selectbox(
                    "Status",
                    ["All", "Pending", "Completed"],
                    index=["All", "Pending", "Completed"].index(st.session_state.filter_status)
                )
                st.session_state.filter_status = status_filter
            
            # Apply filters
            filtered = tasks
            if search:
                filtered = [t for t in filtered if search.lower() in t['title'].lower()]
            if status_filter != "All":
                filtered = [t for t in filtered if t['status'] == status_filter]
            
            if not filtered:
                st.info("No tasks match your criteria")
            
            # Sort by priority and status
            sorted_tasks = sorted(
                filtered,
                key=lambda t: (
                    t['status'] == 'Completed',  # Pending tasks first
                    {"High": 0, "Medium": 1, "Low": 2}[t['priority']],  # Then by priority
                    t['title']  # Then by title
                )
            )
            
            # Display tasks
            for t in sorted_tasks:
                # Create a color indicator based on priority
                priority_colors = {"High": "red", "Medium": "orange", "Low": "blue"}
                status_icon = "✅" if t['status'] == 'Completed' else "⏳"
                
                with st.expander(
                    f"{status_icon} {t['title']} ({t['priority']})",
                    expanded=st.session_state.editing.get(t['id'], False)
                ):
                    # Display details
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.write(f"📝 {t['description']}")
                        st.write(f"🚩 Priority: {t['priority']}")
                        st.write(f"🔁 Type: {t['task_type']}")
                        
                        if t['task_type'] == "One-time":
                            due_date = t['end_date']
                            if due_date:
                                today = date.today()
                                if due_date < today and t['status'] == 'Pending':
                                    st.error(f"📅 Due Date: {due_date} (Overdue)")
                                else:
                                    st.write(f"📅 Due Date: {due_date}")
                                    
                        elif t['task_type'] == "Weekly":
                            st.write(f"🗓 Days: {t['week_days']}")
                        elif t['task_type'] == "Monthly":
                            st.write(f"📆 Day: {t['monthly_date']}")
                        
                        if t['last_completed']:
                            st.write(f"🔥 Last Completed: {t['last_completed']}")
                    
                    with col2:
                        # Action buttons
                        if st.button("✅ Toggle Status", key=f"toggle_{t['id']}", use_container_width=True):
                            new_status = 'Completed' if t['status'] == 'Pending' else 'Pending'
                            last_completed = date.today() if new_status == 'Completed' else None
                            update_task_status(t['id'], new_status, last_completed)
                            st.rerun()
                        
                        if st.button("✏️ Edit", key=f"edit_{t['id']}", use_container_width=True):
                            st.session_state.editing[t['id']] = not st.session_state.editing.get(t['id'], False)
                            st.rerun()
                        
                        if st.button("🗑️ Delete", key=f"delete_{t['id']}", use_container_width=True):
                            delete_task(t['id'])
                            st.success("Task deleted!")
                            st.rerun()
                        
                        # For recurring tasks, allow resetting last completion date
                        if t['task_type'] in ['Daily', 'Weekly', 'Monthly']:
                            if st.button("🔄 Reset", key=f"reset_{t['id']}", use_container_width=True):
                                update_task_status(t['id'], 'Pending', None)
                                st.rerun()
                    
                    # If in edit mode, show inline form
                    if st.session_state.editing.get(t['id'], False):
                        st.markdown("---")
                        st.subheader("Edit Task")
                        
                        new_title = st.text_input("Title", value=t['title'], key=f"title_{t['id']}")
                        new_desc = st.text_area("Description", value=t['description'], key=f"desc_{t['id']}")
                        new_pr = st.selectbox(
                            "Priority", ["Low", "Medium", "High"],
                            index=["Low", "Medium", "High"].index(t['priority']),
                            key=f"pr_{t['id']}"
                        )
                        new_type = st.selectbox(
                            "Task Type", ["One-time", "Daily", "Weekly", "Monthly"],
                            index=["One-time", "Daily", "Weekly", "Monthly"].index(t['task_type']),
                            key=f"type_{t['id']}"
                        )

                        # Conditional edit inputs
                        week_val, month_val, end_val = "", None, None
                        if new_type == "Weekly":
                            week_list = t['week_days'].split(',') if t['week_days'] else []
                            week_val = st.multiselect(
                                "Select Days",
                                ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
                                default=week_list,
                                key=f"week_{t['id']}"
                            )
                            week_val = ",".join(week_val)
                        elif new_type == "Monthly":
                            month_val = st.number_input(
                                "Day of Month", min_value=1, max_value=31, step=1,
                                value=t['monthly_date'] or 1,
                                key=f"month_{t['id']}"
                            )
                        elif new_type == "One-time":
                            end_val = st.date_input(
                                "End Date", value=t['end_date'] or date.today(),
                                key=f"end_{t['id']}"
                            )

                        col1, col2 = st.columns(2)
                        with col1:
                            if st.button("Save Changes", key=f"save_{t['id']}", use_container_width=True):
                                if new_title.strip():
                                    edit_task(
                                        t['id'], new_title, new_desc, new_pr,
                                        new_type, week_val, month_val, end_val
                                    )
                                    st.session_state.editing[t['id']] = False
                                    st.success("Task updated!")
                                    st.rerun()
                                else:
                                    st.error("Title is required")
                        
                        with col2:
                            if st.button("Cancel", key=f"cancel_{t['id']}", use_container_width=True):
                                st.session_state.editing[t['id']] = False
                                st.rerun()

# Initialize scheduler for background notifications
def setup_scheduler():
    try:
        scheduler = BackgroundScheduler()
        # Daily morning summary at 8:00 AM
        scheduler.add_job(send_daily_summary, 'cron', hour=8, minute=0)
        # Evening reminder at 7:00 PM
        scheduler.add_job(send_evening_reminder, 'cron', hour=19, minute=0)
        scheduler.start()
        print("Scheduler started successfully")
        return scheduler
    except Exception as e:
        print(f"Error starting scheduler: {e}")
        return None

if __name__ == "__main__":
    # Setup scheduler if not in Streamlit's development mode
    # This prevents duplicate schedulers when the app reloads during development
    if not st.runtime.exists():
        scheduler = setup_scheduler()
    
    # Run the main app
    main()
