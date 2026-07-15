import os
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple

logger = logging.getLogger("void.founder_assistant")

DB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "memory", "data"))
DB_PATH = os.path.join(DB_DIR, "startups.db")

def init_db():
    """Initialize startups SQLite tables and seed them with high-fidelity realistic datasets."""
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Create SkipIt Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skipit_listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                price_per_day REAL NOT NULL,
                status TEXT NOT NULL,
                owner TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skipit_bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL,
                renter TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT NOT NULL,
                total_price REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (listing_id) REFERENCES skipit_listings(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skipit_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                last_active TEXT NOT NULL
            )
        """)
        
        # 2. Create Smart Cart Tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_cart_stores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_name TEXT NOT NULL,
                location TEXT NOT NULL,
                carts_deployed INTEGER NOT NULL,
                transactions INTEGER NOT NULL,
                checkout_time_secs REAL NOT NULL,
                shrinkage_prevented REAL NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS smart_cart_financials (
                month TEXT PRIMARY KEY, -- YYYY-MM
                revenue REAL NOT NULL,
                operating_cost REAL NOT NULL,
                active_carts INTEGER NOT NULL
            )
        """)
        conn.commit()
        
        # Seed SkipIt Listings
        cursor.execute("SELECT COUNT(*) FROM skipit_listings")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding high-fidelity SkipIt listing inventory.")
            listings = [
                ("Sony A7 IV Mirrorless Camera", "Cameras", 45.0, "ACTIVE", "Karan Johar"),
                ("DeWalt 20V Max Hammer Drill", "Tools", 15.0, "ACTIVE", "Rohan Mehra"),
                ("DJI Mavic 3 Pro Drone", "Cameras", 75.0, "ACTIVE", "Siddharth Malhotra"),
                ("North Face 4-Person Camping Tent", "Outdoor", 20.0, "ACTIVE", "Priya Sharma"),
                ("Oculus Quest 3 VR Headset", "Electronic", 25.0, "ACTIVE", "Aman Verma"),
                ("Bosch Professional Mitre Saw", "Tools", 35.0, "INACTIVE", "Rohan Mehra"),  # Inactive
                ("Patagonia Black Hole Duffel 100L", "Outdoor", 10.0, "ACTIVE", "Vikram Rathore"),
                ("Sennheiser HD 800S Headphones", "Electronic", 50.0, "INACTIVE", "Aditya Roy"), # Inactive
                ("Yeti Tundra 45 Hard Cooler", "Outdoor", 12.0, "ACTIVE", "Nikhil Sen"),
                ("Zoom H6 Handy Audio Recorder", "Cameras", 18.0, "ACTIVE", "Pooja Hegde")
            ]
            cursor.executemany(
                "INSERT INTO skipit_listings (title, category, price_per_day, status, owner) VALUES (?, ?, ?, ?, ?)",
                listings
            )
            conn.commit()
            
        # Seed SkipIt Users (including churned ones)
        cursor.execute("SELECT COUNT(*) FROM skipit_users")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding high-fidelity SkipIt users dataset.")
            today = datetime.now()
            
            def get_past_date(days_offset: int) -> str:
                return (today - timedelta(days=days_offset)).strftime("%Y-%m-%d")
                
            users = [
                ("Mridul Sharma", "mridul@skipit.co", get_past_date(1)), # Active
                ("Ananya Panday", "ananya@bollywood.in", get_past_date(65)), # Churned (>60 days)
                ("Ranbir Kapoor", "ranbir@rkstudios.com", get_past_date(75)), # Churned (>60 days)
                ("Alia Bhatt", "alia@studios.com", get_past_date(12)), # Active
                ("Varun Dhawan", "varun@dhawan.in", get_past_date(61)), # Churned (>60 days)
                ("Deepika Padukone", "deepika@padukone.com", get_past_date(5)), # Active
                ("Kartik Aaryan", "kartik@aaryan.in", get_past_date(92)), # Churned (>60 days)
            ]
            cursor.executemany(
                "INSERT INTO skipit_users (name, email, last_active) VALUES (?, ?, ?)",
                users
            )
            conn.commit()

        # Seed SkipIt Bookings (including bookings created today)
        cursor.execute("SELECT COUNT(*) FROM skipit_bookings")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding SkipIt rentals and bookings data.")
            today = datetime.now()
            today_str = today.strftime("%Y-%m-%d")
            
            # Booking offsets
            bookings = [
                # Bookings today
                (1, "Alia Bhatt", today_str, (today + timedelta(days=2)).strftime("%Y-%m-%d"), 90.0, "COMPLETED", f"{today_str} 09:15"),
                (3, "Deepika Padukone", today_str, (today + timedelta(days=1)).strftime("%Y-%m-%d"), 75.0, "PENDING", f"{today_str} 10:30"),
                (5, "Mridul Sharma", today_str, (today + timedelta(days=3)).strftime("%Y-%m-%d"), 75.0, "COMPLETED", f"{today_str} 08:00"),
                
                # Past bookings
                (2, "Alia Bhatt", (today - timedelta(days=10)).strftime("%Y-%m-%d"), (today - timedelta(days=8)).strftime("%Y-%m-%d"), 30.0, "COMPLETED", (today - timedelta(days=10)).strftime("%Y-%m-%d %H:%M")),
                (4, "Deepika Padukone", (today - timedelta(days=5)).strftime("%Y-%m-%d"), (today - timedelta(days=3)).strftime("%Y-%m-%d"), 40.0, "COMPLETED", (today - timedelta(days=5)).strftime("%Y-%m-%d %H:%M")),
            ]
            cursor.executemany(
                "INSERT INTO skipit_bookings (listing_id, renter, start_date, end_date, total_price, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                bookings
            )
            conn.commit()
            
        # Seed Smart Cart Pilot Stores
        cursor.execute("SELECT COUNT(*) FROM smart_cart_stores")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding Smart Cart hardware retail pilot nodes.")
            stores = [
                ("Delhi Central Hub", "New Delhi, Connaught Place", 15, 1250, 252.0, 2450.0),  # 252 secs = 4.2 mins (vs 480 secs / 8.0 mins baseline)
                ("Noida Retail Center", "Noida, Sector 62", 10, 840, 288.0, 1820.0),      # 288 secs = 4.8 mins
                ("Gurugram Supermart", "Gurugram, Phase 3", 25, 2100, 240.0, 4200.0)      # 240 secs = 4.0 mins
            ]
            cursor.executemany(
                "INSERT INTO smart_cart_stores (store_name, location, carts_deployed, transactions, checkout_time_secs, shrinkage_prevented) VALUES (?, ?, ?, ?, ?, ?)",
                stores
            )
            conn.commit()
            
        # Seed Smart Cart Financials
        cursor.execute("SELECT COUNT(*) FROM smart_cart_financials")
        if cursor.fetchone()[0] == 0:
            logger.info("Seeding Smart Cart operational historical financials.")
            # Last 6 months starting from December 2025
            financials = [
                ("2025-12", 12500.0, 9500.0, 15),
                ("2026-01", 14200.0, 10200.0, 20),
                ("2026-02", 16800.0, 11500.0, 25),
                ("2026-03", 19500.0, 12000.0, 35),
                ("2026-04", 23000.0, 13800.0, 40),
                ("2026-05", 27400.0, 15100.0, 50)
            ]
            cursor.executemany(
                "INSERT INTO smart_cart_financials (month, revenue, operating_cost, active_carts) VALUES (?, ?, ?, ?)",
                financials
            )
            conn.commit()
            
        conn.close()
    except Exception as e:
        logger.error(f"Failed to initialize startups DB: {e}", exc_info=True)

# Initialize on import
init_db()

# ==================== SKIPIT ASSISTANT METHODS ====================

def get_bookings_today() -> Dict[str, Any]:
    """Retrieve count and GTV of bookings created today."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Direct SQL search matching today's date prefix
        cursor.execute(
            "SELECT COUNT(*), SUM(total_price) FROM skipit_bookings WHERE created_at LIKE ?",
            (f"{today_str}%",)
        )
        count, gtv = cursor.fetchone()
        conn.close()
        
        count = count or 0
        gtv = gtv or 0.0
        
        return {
            "status": "ok",
            "message": (
                "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
                f"📊 **SkipIt Bookings Today**: We have captured **{count} active bookings** "
                f"created today, generating a stellar **Gross Transactional Value (GTV) of ${gtv:.2f}**, Sir!"
            ),
            "data": {"count": count, "gtv": gtv}
        }
    except Exception as e:
        logger.error(f"SkipIt bookings today check failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not retrieve bookings: {str(e)}"}

def get_inactive_listings() -> Dict[str, Any]:
    """Retrieve all gear listings currently set as inactive in inventory."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, category, price_per_day, owner FROM skipit_listings WHERE status = 'INACTIVE'")
        rows = cursor.fetchall()
        conn.close()
        
        lines = [
            "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
            "⚠️ **Inactive SkipIt Listings**: The following active gear shares are currently offline, Sir:\n"
        ]
        for row in rows:
            l_id, title, cat, price, owner = row
            lines.append(f"- **{title}** ({cat}) | Owner: *{owner}* | Rate: *${price}/day* (ID: {l_id})")
            
        if not rows:
            lines = [
                "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
                "✅ **All SkipIt Listings Active**: Outstanding, Sir! All rental listings are currently online and earning fees."
            ]
            
        return {
            "status": "ok",
            "message": "\n".join(lines).strip(),
            "data": [
                {"id": r[0], "title": r[1], "category": r[2], "price_per_day": r[3], "owner": r[4]}
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"SkipIt inactive listings lookup failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not retrieve inactive listings: {str(e)}"}

def get_inactive_users(days: int = 60) -> Dict[str, Any]:
    """Identify users who have been inactive for more than a specified threshold of days."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Calculate cut-off date
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.strftime("%Y-%m-%d")
        
        cursor.execute(
            "SELECT id, name, email, last_active FROM skipit_users WHERE last_active <= ? ORDER BY last_active ASC",
            (cutoff_str,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        lines = [
            "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
            f"📉 **Inactive Users (>={days} Days)**: Found **{len(rows)} users** matching churn indicators, Sir:\n"
        ]
        for row in rows:
            u_id, name, email, last_act = row
            # Calculate actual inactive days
            act_dt = datetime.strptime(last_act, "%Y-%m-%d")
            elapsed = (datetime.now() - act_dt).days
            lines.append(f"- **{name}** (*{email}*) — Inactive for **{elapsed} days** *(Last active: {last_act} | ID: {u_id})*")
            
        if not rows:
            lines = [
                "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
                f"✅ **Zero Churned Users**: Excellent! All registered users have been active within the last {days} days, Sir."
            ]
            
        return {
            "status": "ok",
            "message": "\n".join(lines).strip(),
            "data": [
                {"id": r[0], "name": r[1], "email": r[2], "last_active": r[3]}
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"SkipIt inactive users query failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not retrieve inactive users: {str(e)}"}

def generate_weekly_report() -> Dict[str, Any]:
    """Generate a highly polished weekly investor report outlining GTV, list engagement, and churn."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Aggregations
        cursor.execute("SELECT COUNT(*), SUM(total_price) FROM skipit_bookings")
        total_bookings, total_gtv = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM skipit_listings WHERE status = 'ACTIVE'")
        active_listings = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM skipit_users")
        total_users = cursor.fetchone()[0]
        
        # Calculate active user percentage (active in last 30 days)
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM skipit_users WHERE last_active >= ?", (thirty_days_ago,))
        active_users_30d = cursor.fetchone()[0]
        
        conn.close()
        
        total_bookings = total_bookings or 0
        total_gtv = total_gtv or 0.0
        active_user_pct = (active_users_30d / total_users * 100) if total_users else 0.0
        
        report = (
            "The SkipIt Founder Assistant is currently running queries against a local database seeded with mock rental listings and fake user statistics. (Sandbox Mock)\n\n"
            f"📈 **SKIPIT WEEKLY INVESTOR METRICS**\n"
            f"====================================\n"
            f"💰 **Gross Transactional Value (GTV)**: ${total_gtv:.2f}\n"
            f"📦 **Total Rentals Booked**: {total_bookings} units\n"
            f"🟢 **Active Inventory Shared**: {active_listings} items online\n"
            f"👥 **Total User Signups**: {total_users} members\n"
            f"🔄 **User Engagement Rate (30D)**: {active_user_pct:.1f}%\n"
            f"====================================\n"
            f"*Report compiled autonomously by VOID, Sir. Ready to email to seed investors.*"
        )
        
        return {
            "status": "ok",
            "message": report,
            "data": {
                "total_gtv": total_gtv,
                "total_bookings": total_bookings,
                "active_inventory": active_listings,
                "total_users": total_users,
                "engagement_pct": active_user_pct
            }
        }
    except Exception as e:
        logger.error(f"SkipIt weekly report generation failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Weekly report failed: {str(e)}"}

# ==================== SMART CART ASSISTANT METHODS ====================

def get_pilot_performance() -> Dict[str, Any]:
    """Retrieve telemetry metrics for deployed hardware pilot nodes, including speedup and shrinkage."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT id, store_name, location, carts_deployed, transactions, checkout_time_secs, shrinkage_prevented FROM smart_cart_stores")
        rows = cursor.fetchall()
        conn.close()
        
        lines = [
            "The Smart Cart Founder Assistant is currently running queries against a local database seeded with mock store pilot metrics. (Sandbox Mock)\n\n"
            "🛒 **Smart Cart Pilot Performance Metrics**:\n"
        ]
        for row in rows:
            s_id, name, loc, carts, txs, check_time, shrink = row
            # Baseline checkout time is 8.0 minutes (480 seconds)
            baseline = 480.0
            speedup = ((baseline - check_time) / baseline) * 100
            check_mins = check_time / 60.0
            
            lines.append(
                f"🏬 **{name}** ({loc}):\n"
                f"  - 🤖 Deployed Fleet: **{carts} Smart Carts**\n"
                f"  - 💳 Transactions Processed: **{txs} checkouts**\n"
                f"  - ⚡ Avg Checkout: **{check_mins:.1f} minutes** (*{speedup:.1f}% speedup* vs. 8m baseline)\n"
                f"  - 🛡️ Shrinkage Prevented: **${shrink:,.2f}** in retail fraud loss\n"
            )
            
        return {
            "status": "ok",
            "message": "\n".join(lines).strip(),
            "data": [
                {
                    "id": r[0], "store_name": r[1], "carts": r[3], "transactions": r[4],
                    "avg_checkout_mins": r[5]/60.0, "shrinkage_prevented": r[6]
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"Smart Cart pilot performance lookup failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Could not retrieve store performance: {str(e)}"}

def generate_revenue_projections() -> Dict[str, Any]:
    """Perform historical regression projection over financial datasets to forecast revenue for 6 months."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT month, revenue, operating_cost, active_carts FROM smart_cart_financials ORDER BY month ASC")
        rows = cursor.fetchall()
        conn.close()
        
        if len(rows) < 2:
            return {"status": "error", "message": "Insufficient financial historical data to run projections."}
            
        # Calculate month-over-month growth rate
        growth_rates = []
        for i in range(1, len(rows)):
            prev_rev = rows[i-1][1]
            curr_rev = rows[i][1]
            growth_rates.append((curr_rev - prev_rev) / prev_rev)
            
        avg_growth = sum(growth_rates) / len(growth_rates)
        
        # Project next 6 months starting from June 2026
        last_month_str = rows[-1][0] # 2026-05
        last_revenue = rows[-1][1]
        last_cost = rows[-1][2]
        last_carts = rows[-1][3]
        
        last_date = datetime.strptime(last_month_str + "-01", "%Y-%m-%d")
        
        lines = [
            "The Smart Cart Founder Assistant is currently running queries against a local database seeded with mock store pilot metrics. (Sandbox Mock)\n\n"
            f"📊 **Smart Cart Growth Projections (Next 6 Months)**:\n"
            f"Calculated using organic historical revenue growth (*{avg_growth*100:.1f}% MoM*):\n"
        ]
        
        projections_data = []
        
        for m in range(1, 7):
            proj_date = last_date + timedelta(days=31 * m) # Offset by months
            proj_month = proj_date.strftime("%Y-%m-%d")[:7]
            
            # Compound growth
            proj_revenue = last_revenue * ((1 + avg_growth) ** m)
            # Cost scales slightly slower (economy of scale factor 0.85)
            proj_cost = last_cost * ((1 + (avg_growth * 0.85)) ** m)
            proj_margin = proj_revenue - proj_cost
            proj_carts = int(last_carts * ((1 + (avg_growth * 0.5)) ** m))
            
            lines.append(
                f"📅 **{proj_month}**:\n"
                f"  - Revenue: **${proj_revenue:,.2f}**\n"
                f"  - Margin (Net): **${proj_margin:,.2f}** *(Operating Cost: ${proj_cost:,.2f})*\n"
                f"  - Active Deployed Fleet: **{proj_carts} Carts**\n"
            )
            projections_data.append({
                "month": proj_month,
                "projected_revenue": round(proj_revenue, 2),
                "projected_margin": round(proj_margin, 2),
                "projected_carts": proj_carts
            })
            
        return {
            "status": "ok",
            "message": "\n".join(lines).strip(),
            "data": projections_data
        }
    except Exception as e:
        logger.error(f"Smart Cart revenue projections failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Projections calculation failed: {str(e)}"}

def create_store_pitch_deck() -> Dict[str, Any]:
    """Autonomous Store Pitch Deck PowerPoint Compiler utilizing presentation_builder slate-crimson themes."""
    try:
        from tools.presentation_builder import build_presentation
        
        # Build pitch deck specifically optimized for Smart Cart retail stores
        res = build_presentation("Smart Cart Store Pilot")
        
        if res.get("status") == "ok":
            # Enhance message with specialized store pitch details
            filepath = res["message"].split("at **")[1].split("**,")[0]
            msg = (
                "The Smart Cart Founder Assistant is currently running queries against a local database seeded with mock store pilot metrics. (Sandbox Mock)\n\n"
                f"✅ **Smart Cart Store Pitch Deck Compiled successfully, Sir!**\n\n"
                f"I have constructed a high-end, extremely premium **5-slide store pitch deck** "
                f"specifically designed to secure partnerships with leading retail hubs. "
                f"It is saved at **{filepath}** and styled using our signature glowing neon-crimson "
                f"and slate dark glassmorphic layouts. Ready for your executive meetings."
            )
            return {"status": "ok", "message": msg, "data": {"filepath": filepath}}
        else:
            return res
    except Exception as e:
        logger.error(f"Store pitch deck creation failed: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed compiling store pitch deck: {str(e)}"}

# ==================== BUSINESS INTELLIGENCE METHODS ====================

def business_intelligence_recommendations() -> Dict[str, Any]:
    """Correlate metrics from listings, store operations, and user dropoffs to compile BI founder recommendations."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check inactive gear listing counts
        cursor.execute("SELECT COUNT(*) FROM skipit_listings WHERE status = 'INACTIVE'")
        inactive_gear = cursor.fetchone()[0]
        
        # Check user churn rate (inactive > 60 days)
        today = datetime.now()
        cutoff_60d = (today - timedelta(days=60)).strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM skipit_users WHERE last_active <= ?", (cutoff_60d,))
        churn_users = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM skipit_users")
        total_users = cursor.fetchone()[0]
        
        # Check pilot shrinkage
        cursor.execute("SELECT store_name, checkout_time_secs, shrinkage_prevented FROM smart_cart_stores ORDER BY shrinkage_prevented DESC LIMIT 1")
        top_store, avg_time, max_shrink = cursor.fetchone()
        
        conn.close()
        
        churn_pct = (churn_users / total_users * 100) if total_users else 0.0
        
        # Compile strategic BI recommendations
        lines = [
            "Business Intelligence recommendations are generated using mock metrics seeded in a local database. (Sandbox Mock)\n\n"
            f"💡 **VOID AUTONOMOUS FOUNDER RECOMMENDATIONS & BI ANALYTICS**\n",
            f"🔴 **RECOMMENDATION 1 — Churn Prevention Campaign**:\n"
            f"  - *Insight*: **{churn_users} users ({churn_pct:.1f}% of base)** have not logged in or rented in **60+ days**.\n"
            f"  - *Action Plan*: Trigger a re-engagement promo email to this list (e.g. Ranbir Kapoor, Kartik Aaryan) "
            f"offering a **50% discount** on their next premium gear rental. I can compile this template for you.",
            
            f"\n🟡 **RECOMMENDATION 2 — Premium Inventory Optimization**:\n"
            f"  - *Insight*: **{inactive_gear} high-value listings** are currently set to INACTIVE (such as Bosch Mitre Saw).\n"
            f"  - *Action Plan*: Direct-notify the item owners (e.g. Rohan Mehra) reminding them to verify their listing detail. "
            f"An active listing represents up to **$250/month** in average GTV yield.",
            
            f"\n🟢 **RECOMMENDATION 3 — Smart Cart Deployment Reallocation**:\n"
            f"  - *Insight*: Deployed carts at **{top_store}** prevented a significant **${max_shrink:,.2f}** in retail shrinkage, "
            f"maintaining a lightning-fast **{avg_time/60.0:.1f}-minute average checkout speed**.\n"
            f"  - *Action Plan*: Scale cart allocations by transferring 5 units from underutilized Noida pilot stores "
            f"to the DelhiConnaught Connaught Place pilot to maximize ROI and further drop queue bottle-necks."
        ]
        
        return {
            "status": "ok",
            "message": "\n".join(lines).strip(),
            "data": {
                "churn_pct": churn_pct,
                "inactive_listings_cnt": inactive_gear,
                "top_performing_store": top_store
            }
        }
    except Exception as e:
        logger.error(f"BI recommendations computation failed: {e}", exc_info=True)
        return {"status": "error", "message": f"BI computation failed: {str(e)}"}
