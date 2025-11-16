AirStack Space Optimizer

Hackathon Project | A logistics tool for optimizing emergency cargo transport in remote areas.

Live Demo: caee-hackathon-the-moose-team.onrender.com

1. The Problem

In disaster scenarios, remote and rural communities (like those in Alaska) are critically dependent on helicopter transport for emergency supplies. This vital supply chain is plagued with inefficiencies:

Wasted Space: Globally, 30-50% of cargo volume is wasted due to inefficient packing.

Critical Delays: Inefficiencies contribute to 24-48 hour delays in delivering aid.

High Costs: Wasted fuel from poorly optimized loads directly translates to wasted money and resources.

Logistical Hurdles: Ground crews lack the tools to quickly and safely load aircraft based on dynamic supply requests.

2. Our Solution: AirStack

AirStack is a web-based logistics tool designed to solve this problem. It provides a simple interface for administrators to manage cargo requests and a powerful backend to generate optimized loading plans for helicopter crews.

Our solution focuses on maximizing cargo capacity for a UH-60 Black Hawk helicopter, ensuring that every flight delivers the maximum possible aid, saving time, money, and ultimately, lives.

3. Key Features

Admin View:

Submit Cargo Requests: An administrator can add items to a pending list, selecting from preset cargo types (e.g., water, food, first-aid) and assigning a priority level (1-10).

Aircraft Configuration: Pre-filled with the specs for a UH-60 Black Hawk (max weight, length, width, height).

Generate Layout: With a single click, our optimization algorithm processes all pending requests.

Optimization Dashboard: Instantly view the results of the layout, including:

Weight Utilization: See exactly what percentage of the aircraft's weight capacity is used.

Items Packed/Unpacked: Get a clear count of what fit and what's left for the next flight.

Weight Balance: View a balance score and front/rear weight distribution to ensure aircraft safety.

Loading Crew View:

Real-time Plan: Ground crews can access a "Loading Crew View" to see the most recently generated loading plan.

Refresh On-Demand: A refresh button ensures they always have the latest instructions.

Exportable Loading Plans:

2D PDF Slices: Generate a printable PDF that breaks the cargo bay into four vertical slices, showing the ground crew exactly where to place each item.

3D OpenSCAD Model: Export a .scad file to view a complete 3D model of the optimized load.

4. How It Works

The backend is a Flask application that runs a sophisticated optimization algorithm.

Prioritization: The algorithm first sorts all pending cargo requests, prioritizing high-priority items first, then by weight.

Weight Balancing: It intelligently places items to distribute weight evenly across four quadrants of the cargo bay (front-left, front-right, rear-left, rear-right), which is critical for helicopter flight stability.

Packing & Validation: The algorithm places items one by one, checking against the Black Hawk's physical dimensions (length, width, height) and max weight.

Reporting: Once complete, it provides a full report on what was packed, what was left, and the final center of gravity.

5. Technology Stack

Backend: Flask

Frontend: HTML, JavaScript, and Tailwind CSS

PDF Generation: ReportLab

3D Model Generation: OpenSCAD (via text file generation)

Deployment: Gunicorn (on Render)

6. Future Plans

Full Deployment: Deploy at the Bethel Operations Center in Alaska.

Partnerships: Contract with Alaska Homeland Security, Tribal Emergency Response Orgs, and the Alaska National Guard.

Secure Infrastructure: Set up a permanent, secure server with dedicated admin and crew logins.

7. How to Run Locally

Clone the repository:

git clone [https://github.com/your-username/airstack.git](https://github.com/your-username/airstack.git)
cd airstack


Create and activate a virtual environment:

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate


Install dependencies:

pip install -r requirements.txt


Run the application:

# Using Gunicorn (for production-like environment)
gunicorn app:app

# Or using Flask's built-in server (for development)
flask run


Open your browser and navigate to http://127.0.0.1:5000 (or http://127.0.0.1:8000 if using gunicorn).
