from flask import Flask, jsonify, request, send_file
import json
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle

app = Flask(__name__)

# In-memory storage
cargo_requests = []
request_counter = 0
latest_load_plan = None  # Store the latest generated plan for ground crew view

# Item type presets with dimensions in meters and weight in kg
ITEM_PRESETS = {
    "Water Case (24 bottles)": {
        "weight": 18, "length": 0.45, "width": 0.30, "height": 0.25,
        "color": [0.2, 0.5, 0.9]  # Blue
    },
    "Dozen NP Food Cans": {
        "weight": 10, "length": 0.40, "width": 0.30, "height": 0.22,
        "color": [0.8, 0.3, 0.1]  # Orange/Brown
    },
    "First-Aid Kit": {
        "weight": 4, "length": 0.35, "width": 0.25, "height": 0.20,
        "color": [0.9, 0.1, 0.1]  # Red
    },
    "Toilet Paper (12-Roll Pack)": {
        "weight": 3, "length": 0.40, "width": 0.30, "height": 0.25,
        "color": [0.95, 0.95, 0.95]  # White
    },
    "Sanitary Pads (20 Pack)": {
        "weight": 1, "length": 0.30, "width": 0.20, "height": 0.12,
        "color": [0.9, 0.5, 0.8]  # Pink
    },
    "Clothing Pack (Jacket + Undergarments)": {
        "weight": 5, "length": 0.45, "width": 0.35, "height": 0.25,
        "color": [0.3, 0.3, 0.6]  # Dark Blue
    },
    "Blanket (Rolled)": {
        "weight": 2, "length": 0.50, "width": 0.25, "height": 0.25,
        "color": [0.6, 0.4, 0.2]  # Brown
    },
    "Pet Supplies Pack": {
        "weight": 6, "length": 0.50, "width": 0.30, "height": 0.30,
        "color": [0.9, 0.7, 0.2]  # Yellow
    },
    "Baby Formula (Case)": {
        "weight": 8, "length": 0.40, "width": 0.30, "height": 0.25,
        "color": [0.8, 0.9, 0.7]  # Light Green
    }
}

# Aircraft presets with fuel consumption data
AIRCRAFT_PRESETS = {
    "UH-60 Black Hawk": {
        "max_weight": 1200,
        "max_length": 3.8,
        "max_width": 2.2,
        "max_height": 1.3,
        # Fuel consumption in kg/hour
        "fuel_burn_empty": 320,  # Empty weight cruise
        "fuel_burn_per_kg": 0.08,  # Additional fuel per kg of cargo
        "cruise_speed": 268,  # km/h
        "range_full": 592,  # km with full fuel
        "fuel_capacity": 1360  # kg of fuel
    }
}

def calculate_fuel_efficiency(aircraft_type, cargo_weight, mission_distance=100):
    """
    Calculate fuel efficiency metrics for a given cargo load
    
    Args:
        aircraft_type: Aircraft model name
        cargo_weight: Total weight of cargo in kg
        mission_distance: Round-trip distance in km (default 100km)
    
    Returns:
        Dictionary with fuel efficiency metrics
    """
    aircraft = AIRCRAFT_PRESETS.get(aircraft_type)
    if not aircraft:
        return None
    
    # Calculate fuel consumption for this mission
    fuel_burn_empty = aircraft['fuel_burn_empty']
    fuel_burn_per_kg = aircraft['fuel_burn_per_kg']
    cruise_speed = aircraft['cruise_speed']
    
    # Total fuel burn rate (kg/hour)
    total_fuel_burn_rate = fuel_burn_empty + (cargo_weight * fuel_burn_per_kg)
    
    # Flight time for mission (hours)
    flight_time = mission_distance / cruise_speed
    
    # Total fuel used for this trip (kg)
    fuel_used = total_fuel_burn_rate * flight_time
    
    # Fuel efficiency (kg of cargo per kg of fuel)
    fuel_efficiency = cargo_weight / fuel_used if fuel_used > 0 else 0
    
    # Calculate capacity utilization
    capacity_utilization = (cargo_weight / aircraft['max_weight']) * 100
    
    # Correct efficiency logic:
    # 75-85% = Optimal (sweet spot for fuel efficiency)
    # 85%+ = Less efficient per kg (more weight = more fuel per kg, but at least not wasting trips)
    # 60-75% = Moderate (could consolidate better but not terrible)
    # <60% = Inefficient (wasting trips - should consolidate loads)
    if capacity_utilization >= 75 and capacity_utilization <= 85:
        efficiency_rating = "Optimal"
    elif capacity_utilization > 85:
        efficiency_rating = "Good"  # Heavy but no wasted trips
    elif capacity_utilization >= 60:
        efficiency_rating = "Moderate"  # Could consolidate better
    else:
        efficiency_rating = "Low"  # Wasting trips
    
    return {
        "fuel_used_kg": round(fuel_used, 1),
        "fuel_efficiency_ratio": round(fuel_efficiency, 2),
        "efficiency_rating": efficiency_rating,
        "capacity_utilization": round(capacity_utilization, 1)
    }

def get_quantity_from_priority(priority):
    """
    Calculate quantity based on priority level
    Adjusted for fuel efficiency - targeting 75-85% capacity sweet spot (~900-1020kg for UH-60)
    Lower priorities get fewer items to avoid inefficient trips
    """
    quantity_map = {
        1: 3,    # Lowest priority - minimal items
        2: 6,    
        3: 10,   
        4: 15,   
        5: 20,   
        6: 25,   
        7: 30,   
        8: 35,   
        9: 40,   
        10: 50   # Highest priority - full allocation
    }
    return quantity_map.get(priority, 20)

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/api/requests', methods=['GET', 'POST'])
def handle_requests():
    global request_counter, cargo_requests
    
    if request.method == 'POST':
        data = request.json
        item_type = data.get('item_type')
        priority = int(data.get('priority', 1))
        
        # Calculate quantity from priority
        quantity = get_quantity_from_priority(priority)
        
        if item_type not in ITEM_PRESETS:
            return jsonify({"error": "Invalid item type"}), 400
        
        item_specs = ITEM_PRESETS[item_type]
        
        for _ in range(quantity):
            request_counter += 1
            cargo_requests.append({
                "id": request_counter,
                "item_type": item_type,
                "priority": priority,
                "weight": item_specs["weight"],
                "length": item_specs["length"],
                "width": item_specs["width"],
                "height": item_specs["height"]
            })
        
        return jsonify({"success": True, "message": f"Added {quantity} {item_type}(s) (Priority {priority})"})
    
    return jsonify(cargo_requests)

@app.route('/api/requests/clear', methods=['POST'])
def clear_requests():
    global cargo_requests, request_counter
    cargo_requests = []
    request_counter = 0
    return jsonify({"success": True, "message": "All requests cleared"})

@app.route('/api/optimize', methods=['POST'])
def optimize_cargo():
    global latest_load_plan
    
    data = request.json
    max_weight = float(data.get('max_weight', 10000))
    max_length = float(data.get('max_length', 10))
    max_width = float(data.get('max_width', 3))
    max_height = float(data.get('max_height', 2.5))
    
    # Calculate optimal weight range for fuel efficiency (75-85% of max capacity)
    optimal_min_weight = max_weight * 0.75
    optimal_max_weight = max_weight * 0.85
    
    # Sort by priority (descending) then by weight (descending for better balancing)
    sorted_requests = sorted(
        cargo_requests,
        key=lambda x: (-x['priority'], -x['weight']),
        reverse=False
    )
    
    packed = []
    unpacked = []
    current_weight = 0
    current_volume = 0
    max_volume = max_length * max_width * max_height
    
    # Track positions for balanced loading
    # Divide cargo bay into quadrants for weight distribution
    front_left_weight = 0
    front_right_weight = 0
    rear_left_weight = 0
    rear_right_weight = 0
    
    # Group items by priority for preemptive packing
    priority_groups = {}
    for item in sorted_requests:
        priority = item['priority']
        if priority not in priority_groups:
            priority_groups[priority] = []
        priority_groups[priority].append(item)
    
    # Pack items with priority-based weighting
    # Higher priorities get more attempts to pack before lower priorities
    # Priority 10 gets fully processed, then 9, then 8, etc.
    # But we allow some overlap - lower priorities start getting a chance
    # as we progress through higher priority items
    
    items_by_priority = []
    for priority in sorted(priority_groups.keys(), reverse=True):
        items_by_priority.extend([(item, priority) for item in priority_groups[priority]])
    
    # Calculate how many items to attempt from each priority level
    # Higher priorities get processed more aggressively
    total_items = len(items_by_priority)
    packed_items_set = set()
    
    # Track if we've hit optimal fuel efficiency range
    in_optimal_range = False
    
    # Multi-pass packing: each pass focuses on progressively lower priorities
    for pass_num in range(10):
        min_priority_for_pass = 10 - pass_num
        
        for idx, (item, priority) in enumerate(items_by_priority):
            # Skip if already packed
            if idx in packed_items_set:
                continue
            
            # In early passes, only pack high priority items
            # In later passes, allow lower priority items
            if priority < min_priority_for_pass:
                continue
            
            # Check if we're in optimal fuel efficiency range
            if current_weight >= optimal_min_weight and current_weight <= optimal_max_weight:
                in_optimal_range = True
                # Once in optimal range, only pack items if they keep us in range
                # and only if they're high priority (7+)
                if current_weight + item['weight'] > optimal_max_weight:
                    # Would exceed optimal range
                    if priority < 8:  # Only priority 8+ can push past optimal
                        continue
            
            # Try to pack this item
            item_volume = item['length'] * item['width'] * item['height']
            
            # Check if item fits within constraints
            if (current_weight + item['weight'] <= max_weight and
                current_volume + item_volume <= max_volume and
                item['length'] <= max_length and
                item['width'] <= max_width and
                item['height'] <= max_height):
                
                # Find available position with weight balancing
                best_position = find_balanced_position(
                    packed, item, max_length, max_width, max_height, 
                    front_left_weight, front_right_weight, 
                    rear_left_weight, rear_right_weight
                )
                
                if best_position:
                    item_with_pos = item.copy()
                    item_with_pos['position'] = best_position
                    packed.append(item_with_pos)
                    current_weight += item['weight']
                    current_volume += item_volume
                    packed_items_set.add(idx)
                    
                    # Update quadrant weights
                    in_front = best_position['x'] < max_length / 2
                    on_left = best_position['y'] < max_width / 2
                    
                    if in_front and on_left:
                        front_left_weight += item['weight']
                    elif in_front and not on_left:
                        front_right_weight += item['weight']
                    elif not in_front and on_left:
                        rear_left_weight += item['weight']
                    else:
                        rear_right_weight += item['weight']
        
        # If we're in optimal range and have processed high priorities, we can stop
        if in_optimal_range and pass_num >= 3:  # After processing priorities 10, 9, 8, 7
            # Check if there are any critical (priority 9-10) items left
            critical_items_remaining = any(
                idx not in packed_items_set and priority >= 9
                for idx, (item, priority) in enumerate(items_by_priority)
            )
            if not critical_items_remaining:
                break
    
    # Collect unpacked items
    for idx, (item, priority) in enumerate(items_by_priority):
        if idx not in packed_items_set:
            unpacked.append(item)
    
    # Auto top-off: Fill to 75% minimum using priorities 8-10 with proportional distribution
    # If all three priorities exist: ~60% from p10, ~30% from p9, ~10% from p8
    # Rotate through item types to distribute evenly
    optimal_min_weight = max_weight * 0.75
    has_high_priority = any(p >= 8 for p in priority_groups.keys())
    
    if current_weight < optimal_min_weight and has_high_priority:
        # Get priorities 8, 9, 10 that user selected
        high_priorities = sorted([p for p in priority_groups.keys() if p >= 8], reverse=True)
        
        if high_priorities:
            # Calculate how much weight we need to add
            weight_needed = optimal_min_weight - current_weight
            
            # Determine proportional weights based on which priorities exist
            priority_weights = {}
            if 10 in high_priorities and 9 in high_priorities and 8 in high_priorities:
                # All three: 60% / 30% / 10% split
                priority_weights[10] = weight_needed * 0.60
                priority_weights[9] = weight_needed * 0.30
                priority_weights[8] = weight_needed * 0.10
            elif 10 in high_priorities and 9 in high_priorities:
                # Only 10 and 9: 70% / 30% split
                priority_weights[10] = weight_needed * 0.70
                priority_weights[9] = weight_needed * 0.30
            elif 10 in high_priorities and 8 in high_priorities:
                # Only 10 and 8: 80% / 20% split
                priority_weights[10] = weight_needed * 0.80
                priority_weights[8] = weight_needed * 0.20
            elif 9 in high_priorities and 8 in high_priorities:
                # Only 9 and 8: 75% / 25% split
                priority_weights[9] = weight_needed * 0.75
                priority_weights[8] = weight_needed * 0.25
            else:
                # Only one priority: 100%
                priority_weights[high_priorities[0]] = weight_needed
            
            # Track how much weight added per priority
            weight_added_per_priority = {p: 0 for p in high_priorities}
            
            max_topoff_attempts = 1000
            attempts = 0
            
            while current_weight < optimal_min_weight and attempts < max_topoff_attempts:
                attempts += 1
                added_something = False
                
                # Rotate through priorities proportionally, but allow overflow if needed to hit 75%
                for priority in high_priorities:
                    # Allow going over proportional weight if we haven't hit 75% yet
                    # Only enforce proportional limits if we're past 75%
                    if current_weight >= optimal_min_weight:
                        break
                    
                    # Soft limit: prefer proportional distribution but don't stop if under 75%
                    proportion_target = priority_weights.get(priority, weight_needed)
                    
                    items_at_priority = priority_groups[priority]
                    if not items_at_priority:
                        continue
                    
                    # Get all unique item types at this priority
                    unique_types = list(set(item['item_type'] for item in items_at_priority))
                    
                    # Rotate through item types for even distribution
                    item_type = unique_types[attempts % len(unique_types)]
                    item_specs = ITEM_PRESETS[item_type]
                    
                    new_item = {
                        "id": 10000 + attempts,
                        "item_type": item_type,
                        "priority": priority,
                        "weight": item_specs["weight"],
                        "length": item_specs["length"],
                        "width": item_specs["width"],
                        "height": item_specs["height"]
                    }
                    
                    item_volume = new_item['length'] * new_item['width'] * new_item['height']
                    
                    # Check if item fits
                    if (current_weight + new_item['weight'] <= max_weight and
                        current_volume + item_volume <= max_volume and
                        new_item['length'] <= max_length and
                        new_item['width'] <= max_width and
                        new_item['height'] <= max_height):
                        
                        # Find position
                        best_position = find_balanced_position(
                            packed, new_item, max_length, max_width, max_height,
                            front_left_weight, front_right_weight,
                            rear_left_weight, rear_right_weight
                        )
                        
                        if best_position:
                            item_with_pos = new_item.copy()
                            item_with_pos['position'] = best_position
                            packed.append(item_with_pos)
                            current_weight += new_item['weight']
                            current_volume += item_volume
                            weight_added_per_priority[priority] += new_item['weight']
                            added_something = True
                            
                            # Update quadrant weights
                            in_front = best_position['x'] < max_length / 2
                            on_left = best_position['y'] < max_width / 2
                            
                            if in_front and on_left:
                                front_left_weight += new_item['weight']
                            elif in_front and not on_left:
                                front_right_weight += new_item['weight']
                            elif not in_front and on_left:
                                rear_left_weight += new_item['weight']
                            else:
                                rear_right_weight += new_item['weight']
                            
                            # Check if we've reached 75%
                            if current_weight >= optimal_min_weight:
                                break
                    
                    if current_weight >= optimal_min_weight:
                        break
                
                # If we couldn't add anything, stop
                if not added_something:
                    break
            
            # If still below 75% after all attempts, we've hit physical constraints
            # (volume or space limitations)
    
    # Recalculate final center of gravity and balance metrics
    if packed:
        cog_x = sum(p['position']['x'] * p['weight'] for p in packed) / current_weight
        cog_y = sum(p['position']['y'] * p['weight'] for p in packed) / current_weight
        cog_z = sum(p['position']['z'] * p['weight'] for p in packed) / current_weight
        
        # Calculate balance percentage (how close to center in both X and Y)
        balance_x = 100 - (abs(cog_x - max_length/2) / (max_length/2) * 100)
        balance_y = 100 - (abs(cog_y - max_width/2) / (max_width/2) * 100)
        
        balance_score = (balance_x + balance_y) / 2
        
        # Calculate left/right balance
        left_weight = front_left_weight + rear_left_weight
        right_weight = front_right_weight + rear_right_weight
    else:
        cog_x = cog_y = cog_z = 0
        balance_score = 100
        left_weight = right_weight = 0
        front_left_weight = front_right_weight = rear_left_weight = rear_right_weight = 0
    
    weight_utilization = (current_weight / max_weight * 100) if max_weight > 0 else 0
    volume_utilization = (current_volume / max_volume * 100) if max_volume > 0 else 0
    
    # Calculate fuel efficiency for this load
    fuel_metrics = calculate_fuel_efficiency("UH-60 Black Hawk", current_weight)
    
    result = {
        "packed": packed,
        "unpacked": unpacked,
        "stats": {
            "total_weight": current_weight,
            "max_weight": max_weight,
            "weight_utilization": round(weight_utilization, 2),
            "total_volume": current_volume,
            "max_volume": max_volume,
            "volume_utilization": round(volume_utilization, 2),
            "items_packed": len(packed),
            "items_unpacked": len(unpacked),
            "center_of_gravity": {
                "x": round(cog_x, 2),
                "y": round(cog_y, 2),
                "z": round(cog_z, 2)
            },
            "balance_score": round(balance_score, 1),
            "left_weight": round(left_weight, 1),
            "right_weight": round(right_weight, 1)
        },
        "fuel_efficiency": fuel_metrics,
        "aircraft": {
            "type": "UH-60 Black Hawk",
            "max_length": max_length,
            "max_width": max_width,
            "max_height": max_height
        }
    }
    
    # Store for ground crew view
    latest_load_plan = result
    
    return jsonify(result)

def find_balanced_position(packed, item, max_length, max_width, max_height, 
                           front_left_weight, front_right_weight, 
                           rear_left_weight, rear_right_weight):
    """Find the best position for an item considering weight balance in all directions
    Uses MIRRORED LOADING with SOFT ALTERNATING: prefers balanced sides but allows flexibility"""
    item_l = item['length']
    item_w = item['width']
    item_h = item['height']
    item_weight = item['weight']
    
    # Calculate left vs right weight balance
    left_weight = front_left_weight + rear_left_weight
    right_weight = front_right_weight + rear_right_weight
    total_weight = left_weight + right_weight
    
    # Determine quadrant preference based on balance
    # Use SOFT balancing: prefer lighter side but still try all quadrants if needed
    if total_weight == 0:
        # First item - start with front-left
        target_quadrants = [(0, 0), (0, 1), (1, 0), (1, 1)]
    else:
        # Create a prioritized list that prefers lighter side but includes all quadrants
        quadrant_weights = {
            (0, 0): front_left_weight,   # Front-Left
            (0, 1): front_right_weight,  # Front-Right
            (1, 0): rear_left_weight,    # Rear-Left
            (1, 1): rear_right_weight    # Rear-Right
        }
        
        # Sort all quadrants by weight (lightest first)
        # This naturally alternates sides while still trying all options
        target_quadrants = sorted(quadrant_weights.keys(), key=lambda q: quadrant_weights[q])
    
    # Try each quadrant in order of preference
    for rear, right in target_quadrants:
        # Define search area for this quadrant
        x_start = (max_length / 2) if rear else 0
        x_end = max_length if rear else (max_length / 2)
        y_start = (max_width / 2) if right else 0
        y_end = max_width if right else (max_width / 2)
        
        # Grid search within this quadrant
        # MIRRORED LOADING: Left side loads left-to-right, right side loads right-to-left
        step = 0.2  # 20cm steps for better performance
        
        for z in [i * step for i in range(int(max_height / step))]:
            if z + item_h > max_height:
                continue
            
            # Determine Y-axis search direction based on which side we're on
            y_range = [y_start + i * step for i in range(int((y_end - y_start) / step))]
            if right:  # Right side: load from right to left (reverse direction)
                y_range = list(reversed(y_range))
                
            for y in y_range:
                if y + item_w > max_width:
                    continue
                    
                for x in [x_start + i * step for i in range(int((x_end - x_start) / step))]:
                    if x + item_l > max_length:
                        continue
                    
                    # Check position (center of item)
                    pos_x = x + item_l / 2
                    pos_y = y + item_w / 2
                    pos_z = z + item_h / 2
                    
                    # Check if this position overlaps with any packed item
                    overlaps = False
                    for p in packed:
                        if boxes_overlap(
                            x, y, z, item_l, item_w, item_h,
                            p['position']['x'] - p['length']/2,
                            p['position']['y'] - p['width']/2,
                            p['position']['z'] - p['height']/2,
                            p['length'], p['width'], p['height']
                        ):
                            overlaps = True
                            break
                    
                    if not overlaps:
                        return {'x': pos_x, 'y': pos_y, 'z': pos_z}
    
    # If no position found in any quadrant
    return None

def boxes_overlap(x1, y1, z1, l1, w1, h1, x2, y2, z2, l2, w2, h2):
    """Check if two boxes overlap"""
    return not (
        x1 + l1 <= x2 or x2 + l2 <= x1 or
        y1 + w1 <= y2 or y2 + w2 <= y1 or
        z1 + h1 <= z2 or z2 + h2 <= z1
    )

@app.route('/api/latest-plan', methods=['GET'])
def get_latest_plan():
    """API endpoint for ground crew to get the latest load plan"""
    if latest_load_plan:
        return jsonify(latest_load_plan)
    else:
        return jsonify({"error": "No load plan available yet"}), 404

@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    data = request.json
    packed = data.get('packed', [])
    max_length = float(data.get('max_length', 3.8))
    max_width = float(data.get('max_width', 2.2))
    max_height = float(data.get('max_height', 1.3))
    stats = data.get('stats', {})
    
    # Generate PDF
    pdf_buffer = generate_loading_pdf(packed, max_length, max_width, max_height, stats)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='loading_plan.pdf'
    )

def generate_loading_pdf(packed, max_length, max_width, max_height, stats):
    """Generate a 4-page PDF showing vertical slices of cargo bay"""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Define quarters (vertical slices along length)
    quarter_width = max_length / 4
    
    for quarter in range(4):
        # Calculate slice boundaries
        slice_start = quarter * quarter_width
        slice_end = (quarter + 1) * quarter_width
        
        # Filter items in this slice
        items_in_slice = []
        for item in packed:
            item_x = item['position']['x']
            item_length = item['length']
            item_start = item_x - item_length/2
            item_end = item_x + item_length/2
            
            # Check if item overlaps with this slice
            if item_start < slice_end and item_end > slice_start:
                items_in_slice.append(item)
        
        # Draw page header
        c.setFont("Helvetica-Bold", 20)
        c.drawString(50, height - 50, f"AirStack Loading Plan - Slice {quarter + 1} of 4")
        
        c.setFont("Helvetica", 12)
        c.drawString(50, height - 75, f"UH-60 Black Hawk")
        c.drawString(50, height - 92, f"Length Section: {slice_start:.2f}m - {slice_end:.2f}m")
        
        # Draw stats
        c.setFont("Helvetica", 10)
        c.drawString(400, height - 75, f"Total Weight: {stats.get('total_weight', 0):.1f} / {stats.get('max_weight', 0):.0f} kg")
        c.drawString(400, height - 92, f"Items in Slice: {len(items_in_slice)}")
        c.drawString(400, height - 109, f"Balance Score: {stats.get('balance_score', 0):.1f}%")
        
        cog = stats.get('center_of_gravity', {})
        c.drawString(400, height - 126, f"CoG: X:{cog.get('x', 0):.1f} Y:{cog.get('y', 0):.1f} Z:{cog.get('z', 0):.1f}m")
        
        # Draw cargo bay outline (top view)
        bay_draw_height = 400
        bay_draw_width = 500
        bay_x = 50
        bay_y = height - 550
        
        # Scale factors
        scale_w = bay_draw_width / max_width
        scale_h = bay_draw_height / max_height
        
        # Draw bay outline
        c.setStrokeColor(colors.black)
        c.setLineWidth(2)
        c.rect(bay_x, bay_y, bay_draw_width, bay_draw_height)
        
        # Add axis labels
        c.setFont("Helvetica", 10)
        c.drawString(bay_x + bay_draw_width/2 - 20, bay_y - 20, "Width (m)")
        c.saveState()
        c.translate(bay_x - 30, bay_y + bay_draw_height/2)
        c.rotate(90)
        c.drawString(-30, 0, "Height (m)")
        c.restoreState()
        
        # Draw grid
        c.setStrokeColor(colors.lightgrey)
        c.setLineWidth(0.5)
        for i in range(1, int(max_width) + 1):
            x = bay_x + i * scale_w
            c.line(x, bay_y, x, bay_y + bay_draw_height)
        for i in range(1, int(max_height) + 1):
            y = bay_y + i * scale_h
            c.line(bay_x, y, bay_x + bay_draw_width, y)
        
        # Draw items in this slice
        for idx, item in enumerate(items_in_slice):
            pos_y = item['position']['y']
            pos_z = item['position']['z']
            item_width = item['width']
            item_height = item['height']
            
            # Calculate box position (centered)
            box_x = bay_x + (pos_y - item_width/2) * scale_w
            box_y = bay_y + (pos_z - item_height/2) * scale_h
            box_w = item_width * scale_w
            box_h = item_height * scale_h
            
            # Get color from item type
            item_type = item['item_type']
            if item_type in ITEM_PRESETS and 'color' in ITEM_PRESETS[item_type]:
                rgb = ITEM_PRESETS[item_type]['color']
                color = colors.Color(rgb[0], rgb[1], rgb[2])
            else:
                # Fallback to gray
                color = colors.grey
            
            # Draw box
            c.setFillColor(color)
            c.setStrokeColor(colors.black)
            c.setLineWidth(1.5)
            c.rect(box_x, box_y, box_w, box_h, fill=1, stroke=1)
            
            # Draw label
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 8)
            label = f"ID{item['id']}"
            c.drawCentredString(box_x + box_w/2, box_y + box_h/2 + 8, label)
            
            c.setFont("Helvetica", 7)
            weight = f"{item['weight']}kg"
            c.drawCentredString(box_x + box_w/2, box_y + box_h/2 - 2, weight)
            
            item_name = item['item_type']
            if len(item_name) > 15:
                item_name = item_name[:12] + "..."
            c.drawCentredString(box_x + box_w/2, box_y + box_h/2 - 12, item_name)
        
        # Draw legend
        legend_y = 150
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, legend_y, "Items in This Slice:")
        
        c.setFont("Helvetica", 9)
        legend_y -= 20
        
        for idx, item in enumerate(items_in_slice):
            if legend_y < 50:  # Don't overflow page
                c.drawString(50, legend_y, "...and more")
                break
            
            # Get color from item type
            item_type = item['item_type']
            if item_type in ITEM_PRESETS and 'color' in ITEM_PRESETS[item_type]:
                rgb = ITEM_PRESETS[item_type]['color']
                color = colors.Color(rgb[0], rgb[1], rgb[2])
            else:
                color = colors.grey
            
            c.setFillColor(color)
            c.rect(50, legend_y - 8, 12, 12, fill=1, stroke=1)
            
            c.setFillColor(colors.black)
            text = f"ID{item['id']}: {item['item_type']} - {item['weight']}kg - Priority {item['priority']}"
            c.drawString(70, legend_y - 4, text)
            legend_y -= 18
        
        # Add page number
        c.setFont("Helvetica", 10)
        c.drawString(width - 100, 30, f"Page {quarter + 1} of 4")
        
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer

@app.route('/api/export-openscad', methods=['POST'])
def export_openscad():
    data = request.json
    packed = data.get('packed', [])
    max_length = float(data.get('max_length', 10))
    max_width = float(data.get('max_width', 3))
    max_height = float(data.get('max_height', 2.5))
    stats = data.get('stats', {})
    
    # Generate OpenSCAD code
    scad_code = generate_openscad(packed, max_length, max_width, max_height, stats)
    
    # Create file in memory
    output = io.BytesIO()
    output.write(scad_code.encode('utf-8'))
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/plain',
        as_attachment=True,
        download_name='cargo_manifest.scad'
    )

def generate_openscad(packed, max_length, max_width, max_height, stats):
    """Generate OpenSCAD code with semi-cylindrical cargo bay"""
    
    # Convert meters to mm for better OpenSCAD visualization
    scale = 1000
    
    scad = """// Military Cargo Loading Manifest
// Generated by Space Optimizer

"""
    
    # Add statistics as comments
    scad += f"""// === CARGO STATISTICS ===
// Total Weight: {stats.get('total_weight', 0):.1f} kg / {stats.get('max_weight', 0):.0f} kg
// Weight Utilization: {stats.get('weight_utilization', 0):.2f}%
// Volume Utilization: {stats.get('volume_utilization', 0):.2f}%
// Items Packed: {stats.get('items_packed', 0)}
// Items Unpacked: {stats.get('items_unpacked', 0)}

"""
    
    # OpenSCAD parameters - increase dimensions by 25% for better visibility
    scad += f"""// === CARGO BAY DIMENSIONS (mm) ===
// Note: Dimensions increased by 25% for better visualization
bay_length = {max_length * scale * 1.25};
bay_width = {max_width * scale * 1.25};
bay_height = {max_height * scale * 1.5};  // Extra height for top clearance
wall_thickness = 20;

// Text settings
text_size = 50;
text_depth = 2;

$fn = 50; // Smooth curves

"""
    
    # Module for semi-cylindrical cargo bay
    scad += """// === SEMI-CYLINDRICAL CARGO BAY ===
module cargo_bay() {
    color([0.3, 0.3, 0.3, 0.3]) {
        difference() {
            // Outer semi-cylinder
            translate([bay_length/2, bay_width/2, 0])
                rotate([0, 90, 0])
                    intersection() {
                        cylinder(h=bay_length, r=bay_width/2, center=true);
                        translate([0, 0, 0])
                            cube([bay_width, bay_width, bay_length + 10], center=true);
                    }
            
            // Inner hollow
            translate([bay_length/2, bay_width/2, wall_thickness])
                rotate([0, 90, 0])
                    intersection() {
                        cylinder(h=bay_length + 10, r=bay_width/2 - wall_thickness, center=true);
                        translate([0, 0, 0])
                            cube([bay_width, bay_width, bay_length + 20], center=true);
                    }
            
            // Front opening
            translate([-5, bay_width/2, bay_height/2])
                cube([20, bay_width + 10, bay_height + 10], center=true);
        }
        
        // Floor
        translate([bay_length/2, bay_width/2, -wall_thickness/2])
            cube([bay_length, bay_width, wall_thickness], center=true);
    }
}

"""
    
    # Module for cargo box with label
    scad += """// === CARGO BOX MODULE ===
module cargo_box(x, y, z, l, w, h, color_vec, label_text, weight_text) {
    translate([x, y, z]) {
        // Box
        color(color_vec)
            cube([l, w, h], center=true);
        
        // Box edges
        color([0, 0, 0])
            translate([0, 0, 0]) {
                // Edge wireframe
                edge_r = 2;
                
                // Bottom edges
                translate([0, 0, -h/2]) {
                    translate([l/2, 0, 0]) rotate([0, 90, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([-l/2, 0, 0]) rotate([0, 90, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([0, w/2, 0]) rotate([90, 0, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([0, -w/2, 0]) rotate([90, 0, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                }
                
                // Top edges
                translate([0, 0, h/2]) {
                    translate([l/2, 0, 0]) rotate([0, 90, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([-l/2, 0, 0]) rotate([0, 90, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([0, w/2, 0]) rotate([90, 0, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                    translate([0, -w/2, 0]) rotate([90, 0, 0]) cylinder(h=edge_r, r=edge_r, center=true);
                }
            }
        
        // Label on top
        color([1, 1, 1])
            translate([0, 0, h/2 + text_depth/2])
                linear_extrude(height=text_depth)
                    text(label_text, size=text_size, halign="center", valign="center", font="Liberation Sans:style=Bold");
        
        // Weight label on side
        color([1, 1, 0])
            translate([0, -w/2 - text_depth/2, 0])
                rotate([90, 0, 0])
                    linear_extrude(height=text_depth)
                        text(weight_text, size=text_size * 0.7, halign="center", valign="center", font="Liberation Sans:style=Bold");
    }
}

"""
    
    # Main assembly
    scad += """// === MAIN ASSEMBLY ===
cargo_bay();

"""
    
    for idx, item in enumerate(packed):
        # Get color from item type
        item_type = item['item_type']
        if item_type in ITEM_PRESETS and 'color' in ITEM_PRESETS[item_type]:
            rgb = ITEM_PRESETS[item_type]['color']
            color = f"[{rgb[0]}, {rgb[1]}, {rgb[2]}, 0.8]"
        else:
            # Fallback to blue if color not found
            color = "[0.5, 0.5, 0.8, 0.8]"
        
        # Convert position and dimensions to mm
        # Scale up by 1.25 to match the larger bay
        x = item['position']['x'] * scale * 1.25
        y = item['position']['y'] * scale * 1.25
        z = item['position']['z'] * scale * 1.5  # Height scaled 1.5x
        l = item['length'] * scale
        w = item['width'] * scale
        h = item['height'] * scale
        
        # Create label
        label = f"ID{item['id']}"
        weight_label = f"{item['weight']}kg"
        
        scad += f"""// Item {item['id']}: {item['item_type']} (Priority: {item['priority']})
cargo_box({x}, {y}, {z}, {l}, {w}, {h}, {color}, "{label}", "{weight_label}");

"""
    
    # Add legend/info panel
    scad += f"""
// === INFO PANEL ===
color([0.2, 0.2, 0.2, 0.9])
    translate([bay_length + 500, bay_width/2, bay_height/2])
        cube([800, bay_width * 1.5, bay_height * 1.2], center=true);

color([1, 1, 1])
    translate([bay_length + 500, bay_width/2, bay_height/2 + 300])
        linear_extrude(height=5)
            text("CARGO MANIFEST", size=80, halign="center", valign="center", font="Liberation Sans:style=Bold");

color([0.8, 0.8, 0.8]) {{
    translate([bay_length + 500, bay_width/2, bay_height/2 + 150])
        linear_extrude(height=5)
            text("Weight: {stats.get('total_weight', 0):.0f}/{stats.get('max_weight', 0):.0f} kg", size=50, halign="center", valign="center");
    
    translate([bay_length + 500, bay_width/2, bay_height/2 + 50])
        linear_extrude(height=5)
            text("Util: {stats.get('weight_utilization', 0):.1f}%", size=50, halign="center", valign="center");
    
    translate([bay_length + 500, bay_width/2, bay_height/2 - 50])
        linear_extrude(height=5)
            text("Packed: {stats.get('items_packed', 0)}", size=50, halign="center", valign="center");
    
    translate([bay_length + 500, bay_width/2, bay_height/2 - 150])
        linear_extrude(height=5)
            text("Unpacked: {stats.get('items_unpacked', 0)}", size=50, halign="center", valign="center");
}}
"""
    
    return scad

@app.route('/api/item-presets', methods=['GET'])
def get_item_presets():
    return jsonify(ITEM_PRESETS)

@app.route('/api/aircraft-presets', methods=['GET'])
def get_aircraft_presets():
    return jsonify(AIRCRAFT_PRESETS)


HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AirStack Space Optimizer</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 text-gray-800 min-h-screen">
    <div class="container mx-auto px-4 py-8">
        <header class="mb-8 flex items-center gap-6">
            <div class="flex items-center">
                <span class="text-6xl font-bold" style="color: #72A7C0;">Air</span>
                <span class="text-6xl font-bold" style="color: #5B6466;">Stack</span>
            </div>
            <div class="border-l-2 border-gray-300 pl-6">
                <h1 class="text-3xl font-bold" style="color: #5B6466;">Space Optimizer</h1>
            </div>
        </header>

        <div class="mb-6 flex gap-4">
            <button onclick="switchView('admin')" id="adminViewBtn" class="px-6 py-3 rounded-lg font-semibold transition text-white" style="background-color: #72A7C0;">
                Admin View
            </button>
            <button onclick="switchView('loadingcrew')" id="loadingCrewViewBtn" class="px-6 py-3 rounded-lg font-semibold transition" style="background-color: #E5E5E5; color: #5B6466;">
                Loading Crew View
            </button>
        </div>

        <div id="adminView" class="space-y-6">
            <div class="bg-white rounded-lg p-6 shadow-lg border border-gray-200">
                <h2 class="text-2xl font-bold mb-4" style="color: #72A7C0;">Submit Cargo Request</h2>
                <form id="cargoForm" class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Item Type</label>
                        <select id="itemType" class="w-full bg-white border-2 border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-400">
                            <option value="">Select Item...</option>
                        </select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Priority (1-10)</label>
                        <input type="number" id="priority" min="1" max="10" value="5" class="w-full bg-white border-2 border-gray-300 rounded px-3 py-2 focus:outline-none focus:border-blue-400">
                    </div>
                    <div class="flex items-end">
                        <button type="submit" class="w-full text-white font-bold py-2 px-4 rounded transition" style="background-color: #5B6466;">
                            Add Request
                        </button>
                    </div>
                </form>
            </div>

            <div class="bg-white rounded-lg p-6 shadow-lg border border-gray-200">
                <h2 class="text-2xl font-bold mb-4" style="color: #72A7C0;">Pending Requests</h2>
                <div class="overflow-x-auto">
                    <table class="w-full text-left">
                        <thead style="background-color: #F2F2F0;">
                            <tr>
                                <th class="px-4 py-2" style="color: #5B6466;">Item Type</th>
                                <th class="px-4 py-2" style="color: #5B6466;">Priority</th>
                                <th class="px-4 py-2" style="color: #5B6466;">Quantity</th>
                                <th class="px-4 py-2" style="color: #5B6466;">Weight (kg)</th>
                                <th class="px-4 py-2" style="color: #5B6466;">Dimensions (m)</th>
                            </tr>
                        </thead>
                        <tbody id="requestsTable" class="divide-y divide-gray-200">
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Aircraft Configuration Section -->
            <div class="bg-white rounded-lg p-6 shadow-lg border border-gray-200">
                <h2 class="text-2xl font-bold mb-4" style="color: #72A7C0;">Aircraft Configuration</h2>
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                    <div class="md:col-span-3">
                        <label class="block text-sm font-medium mb-2 text-gray-700">Aircraft Type</label>
                        <input type="text" value="UH-60 Black Hawk" readonly class="w-full bg-gray-100 border-2 border-gray-300 rounded px-3 py-2 cursor-not-allowed text-gray-700 font-semibold">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Max Weight (kg)</label>
                        <input type="text" value="1200" readonly class="w-full bg-gray-100 border-2 border-gray-300 rounded px-3 py-2 cursor-not-allowed text-gray-700">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Max Length (m)</label>
                        <input type="text" value="3.8" readonly class="w-full bg-gray-100 border-2 border-gray-300 rounded px-3 py-2 cursor-not-allowed text-gray-700">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Max Width (m)</label>
                        <input type="text" value="2.2" readonly class="w-full bg-gray-100 border-2 border-gray-300 rounded px-3 py-2 cursor-not-allowed text-gray-700">
                    </div>
                    <div>
                        <label class="block text-sm font-medium mb-2 text-gray-700">Max Height (m)</label>
                        <input type="text" value="1.3" readonly class="w-full bg-gray-100 border-2 border-gray-300 rounded px-3 py-2 cursor-not-allowed text-gray-700">
                    </div>
                </div>
                <button onclick="generateManifest()" class="w-full text-white font-bold py-4 px-6 rounded-lg text-xl transition" style="background-color: #72A7C0;">
                    Generate Layout
                </button>
            </div>

            <div id="resultsSection" class="space-y-6 hidden">
                <div class="bg-white rounded-lg p-6 shadow-lg border border-gray-200">
                    <h2 class="text-2xl font-bold mb-4" style="color: #5B6466;">Export Ready</h2>
                    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                        <div class="rounded p-4" style="background-color: #F2F2F0;">
                            <div class="text-sm" style="color: #5B6466;">Weight Used</div>
                            <div class="text-xl font-bold" id="weightUsed" style="color: #5B6466;">0 kg</div>
                        </div>
                        <div class="rounded p-4" style="background-color: #F2F2F0;">
                            <div class="text-sm" style="color: #5B6466;">Weight Utilization</div>
                            <div class="text-xl font-bold" id="weightUtil" style="color: #5B6466;">0%</div>
                        </div>
                        <div class="rounded p-4" style="background-color: #F2F2F0;">
                            <div class="text-sm" style="color: #5B6466;">Items Packed</div>
                            <div class="text-xl font-bold" id="packedCount" style="color: #72A7C0;">0</div>
                        </div>
                        <div class="rounded p-4" style="background-color: #F2F2F0;">
                            <div class="text-sm" style="color: #5B6466;">Items Unpacked</div>
                            <div class="text-xl font-bold text-red-600" id="unpackedCount">0</div>
                        </div>
                    </div>
                    
                    <div class="bg-blue-50 border-2 border-blue-200 rounded-lg p-4 mb-6">
                        <h3 class="font-bold text-lg mb-3" style="color: #5B6466;">Weight Balance</h3>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
                            <div>
                                <div class="text-sm text-gray-600">Balance Score</div>
                                <div class="text-2xl font-bold" id="balanceScore" style="color: #72A7C0;">100%</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-600">Front Weight</div>
                                <div class="text-xl font-bold" id="leftWeight" style="color: #5B6466;">0 kg</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-600">Rear Weight</div>
                                <div class="text-xl font-bold" id="rightWeight" style="color: #5B6466;">0 kg</div>
                            </div>
                        </div>
                        <div class="mt-3 text-sm text-gray-600">
                            Center of Gravity: <span id="cogDisplay" class="font-mono">-</span>
                        </div>
                    </div>
                    
                    <div class="bg-green-50 border-2 border-green-200 rounded-lg p-4 mb-6">
                        <h3 class="font-bold text-lg mb-3" style="color: #5B6466;">Fuel Efficiency</h3>
                        <div class="grid grid-cols-2 md:grid-cols-3 gap-4">
                            <div>
                                <div class="text-sm text-gray-600">Fuel This Trip</div>
                                <div class="text-xl font-bold" id="fuelUsed" style="color: #5B6466;">0 kg</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-600">Efficiency Rating</div>
                                <div class="text-lg font-bold" id="efficiencyRating" style="color: #5B6466;">-</div>
                            </div>
                            <div>
                                <div class="text-sm text-gray-600">Cargo/Fuel Ratio</div>
                                <div class="text-xl font-bold" id="fuelEfficiencyRatio" style="color: #5B6466;">0</div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="space-y-3">
                        <button onclick="downloadPDF()" class="w-full text-white font-bold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2" style="background-color: #72A7C0;">
                            Download Loading Plan PDF (Ground Crew)
                        </button>
                        <button onclick="downloadOpenSCAD()" class="w-full text-white font-bold py-3 px-6 rounded-lg transition flex items-center justify-center gap-2" style="background-color: #5B6466;">
                            Download OpenSCAD File (.scad)
                        </button>
                    </div>
                    
                    <p class="text-sm text-gray-600 mt-4">
                        Download the ground crew loading plan (PDF with 4 vertical slices) or the 3D model (OpenSCAD).
                    </p>
                </div>
            </div>

            <div class="flex gap-4">
                <button onclick="clearAllRequests()" class="flex-1 bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-lg transition">
                    Clear All Requests
                </button>
            </div>
        </div>

        <div id="loadingCrewView" class="space-y-6 hidden">
            <div class="bg-white rounded-lg p-6 shadow-lg border border-gray-200">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-2xl font-bold" style="color: #72A7C0;">Current Loading Plan</h2>
                    <button onclick="refreshLoadingCrewView()" class="px-4 py-2 text-white rounded-lg transition" style="background-color: #72A7C0;">
                        Refresh
                    </button>
                </div>
                
                <div id="noPlanMessage" class="text-center py-12 text-gray-500">
                    <p class="text-xl mb-2">No loading plan available yet</p>
                    <p class="text-sm">Waiting for admin to generate a layout...</p>
                </div>
                
                <div id="planContent" class="hidden">
                    <!-- PDF Viewer - 4 slice images displayed here -->
                    <div id="pdfSlices" class="space-y-6">
                        <!-- Slices will be rendered as canvases here -->
                    </div>
                    
                    <div class="mt-6">
                        <button onclick="downloadLoadingCrewPDF()" class="w-full text-white font-bold py-4 px-6 rounded-lg text-xl transition flex items-center justify-center gap-2" style="background-color: #72A7C0;">
                            Download Complete Loading Plan PDF
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let itemPresets = {};
        let aircraftPresets = {};
        let lastOptimizationResult = null;
        let lastAircraftConfig = null;

        async function init() {
            await loadItemPresets();
            await loadAircraftPresets();
            await loadRequests();
        }

        async function loadItemPresets() {
            const response = await fetch('/api/item-presets');
            itemPresets = await response.json();
            
            const select = document.getElementById('itemType');
            Object.keys(itemPresets).forEach(item => {
                const option = document.createElement('option');
                option.value = item;
                option.textContent = item;
                select.appendChild(option);
            });
        }

        async function loadAircraftPresets() {
            const response = await fetch('/api/aircraft-presets');
            aircraftPresets = await response.json();
        }

        function switchView(view) {
            if (view === 'admin') {
                document.getElementById('adminView').classList.remove('hidden');
                document.getElementById('loadingCrewView').classList.add('hidden');
                document.getElementById('adminViewBtn').style.backgroundColor = '#72A7C0';
                document.getElementById('adminViewBtn').style.color = 'white';
                document.getElementById('loadingCrewViewBtn').style.backgroundColor = '#E5E5E5';
                document.getElementById('loadingCrewViewBtn').style.color = '#5B6466';
                loadRequests();
            } else if (view === 'loadingcrew') {
                document.getElementById('adminView').classList.add('hidden');
                document.getElementById('loadingCrewView').classList.remove('hidden');
                document.getElementById('loadingCrewViewBtn').style.backgroundColor = '#72A7C0';
                document.getElementById('loadingCrewViewBtn').style.color = 'white';
                document.getElementById('adminViewBtn').style.backgroundColor = '#E5E5E5';
                document.getElementById('adminViewBtn').style.color = '#5B6466';
                loadLoadingCrewPlan();
            }
        }

        document.getElementById('cargoForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const itemType = document.getElementById('itemType').value;
            const priority = document.getElementById('priority').value;
            
            if (!itemType) {
                alert('Please select an item type');
                return;
            }
            
            try {
                const response = await fetch('/api/requests', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ item_type: itemType, priority })
                });
                
                const result = await response.json();
                if (result.success) {
                    // Silently update - no alert popup
                    // Don't reset the form, just clear the item selection
                    document.getElementById('itemType').value = '';
                    await loadRequests();
                } else {
                    alert('Error adding request: ' + (result.error || 'Unknown error'));
                }
            } catch (error) {
                console.error('Error adding request:', error);
                alert('Error adding request. Please try again.');
            }
        });

        async function loadRequests() {
            const response = await fetch('/api/requests');
            const requests = await response.json();
            
            const tbody = document.getElementById('requestsTable');
            tbody.innerHTML = '';
            
            // Group requests by item_type and priority
            const grouped = {};
            requests.forEach(req => {
                const key = `${req.item_type}_${req.priority}`;
                if (!grouped[key]) {
                    grouped[key] = {
                        item_type: req.item_type,
                        priority: req.priority,
                        weight: req.weight,
                        length: req.length,
                        width: req.width,
                        height: req.height,
                        count: 0
                    };
                }
                grouped[key].count++;
            });
            
            // Display grouped items
            Object.values(grouped).forEach(item => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-gray-50';
                row.innerHTML = `
                    <td class="px-4 py-2">${item.item_type}</td>
                    <td class="px-4 py-2">
                        <span class="px-2 py-1 rounded text-xs font-bold ${getPriorityColor(item.priority)}">
                            ${item.priority}
                        </span>
                    </td>
                    <td class="px-4 py-2 font-semibold">${item.count}</td>
                    <td class="px-4 py-2">${item.weight}</td>
                    <td class="px-4 py-2">${item.length} × ${item.width} × ${item.height}</td>
                `;
                tbody.appendChild(row);
            });
        }

        function getPriorityColor(priority) {
            if (priority >= 8) return 'bg-red-600 text-white';
            if (priority >= 5) return 'bg-yellow-600 text-white';
            return 'bg-green-600 text-white';
        }

        async function generateManifest() {
            // Use locked UH-60 Black Hawk specs
            const maxWeight = 1200;
            const maxLength = 3.8;
            const maxWidth = 2.2;
            const maxHeight = 1.3;
            
            try {
                const response = await fetch('/api/optimize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        max_weight: maxWeight,
                        max_length: maxLength,
                        max_width: maxWidth,
                        max_height: maxHeight
                    })
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                lastOptimizationResult = result;
                lastAircraftConfig = {
                    max_weight: maxWeight,
                    max_length: maxLength,
                    max_width: maxWidth,
                    max_height: maxHeight
                };
                
                displayResults(result);
            } catch (error) {
                console.error('Error generating manifest:', error);
                alert('Error generating layout. Please check the console for details.');
            }
        }

        function displayResults(result) {
            document.getElementById('resultsSection').classList.remove('hidden');
            
            document.getElementById('weightUsed').textContent = `${result.stats.total_weight.toFixed(1)} kg`;
            document.getElementById('weightUtil').textContent = `${result.stats.weight_utilization}%`;
            document.getElementById('packedCount').textContent = result.stats.items_packed;
            document.getElementById('unpackedCount').textContent = result.stats.items_unpacked;
            
            // Display balance information
            document.getElementById('balanceScore').textContent = `${result.stats.balance_score}%`;
            document.getElementById('leftWeight').textContent = `${result.stats.left_weight} kg`;
            document.getElementById('rightWeight').textContent = `${result.stats.right_weight} kg`;
            
            const cog = result.stats.center_of_gravity;
            document.getElementById('cogDisplay').textContent = `X:${cog.x}m Y:${cog.y}m Z:${cog.z}m`;
            
            // Display fuel efficiency information
            if (result.fuel_efficiency) {
                document.getElementById('fuelUsed').textContent = `${result.fuel_efficiency.fuel_used_kg} kg`;
                document.getElementById('efficiencyRating').textContent = result.fuel_efficiency.efficiency_rating;
                document.getElementById('fuelEfficiencyRatio').textContent = result.fuel_efficiency.fuel_efficiency_ratio.toFixed(2);
            }
            
            // Update the requests table to show actual packed quantities (including auto-filled)
            updateRequestsTableWithActuals(result.packed);
        }
        
        function updateRequestsTableWithActuals(packedItems) {
            const tbody = document.getElementById('requestsTable');
            tbody.innerHTML = '';
            
            // Group packed items by item_type and priority
            const grouped = {};
            packedItems.forEach(item => {
                const key = `${item.item_type}_${item.priority}`;
                if (!grouped[key]) {
                    grouped[key] = {
                        item_type: item.item_type,
                        priority: item.priority,
                        weight: item.weight,
                        length: item.length,
                        width: item.width,
                        height: item.height,
                        count: 0
                    };
                }
                grouped[key].count++;
            });
            
            // Display grouped items
            Object.values(grouped).forEach(item => {
                const row = document.createElement('tr');
                row.className = 'hover:bg-gray-50';
                row.innerHTML = `
                    <td class="px-4 py-2">${item.item_type}</td>
                    <td class="px-4 py-2">
                        <span class="px-2 py-1 rounded text-xs font-bold ${getPriorityColor(item.priority)}">
                            ${item.priority}
                        </span>
                    </td>
                    <td class="px-4 py-2 font-semibold">${item.count}</td>
                    <td class="px-4 py-2">${item.weight}</td>
                    <td class="px-4 py-2">${item.length} × ${item.width} × ${item.height}</td>
                `;
                tbody.appendChild(row);
            });
        }

        async function downloadOpenSCAD() {
            if (!lastOptimizationResult || !lastAircraftConfig) {
                alert('Please generate a manifest first');
                return;
            }
            
            const response = await fetch('/api/export-openscad', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    packed: lastOptimizationResult.packed,
                    max_length: lastAircraftConfig.max_length,
                    max_width: lastAircraftConfig.max_width,
                    max_height: lastAircraftConfig.max_height,
                    stats: lastOptimizationResult.stats
                })
            });
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'cargo_manifest.scad';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }

        async function downloadPDF() {
            if (!lastOptimizationResult || !lastAircraftConfig) {
                alert('Please generate a manifest first');
                return;
            }
            
            const response = await fetch('/api/export-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    packed: lastOptimizationResult.packed,
                    max_length: lastAircraftConfig.max_length,
                    max_width: lastAircraftConfig.max_width,
                    max_height: lastAircraftConfig.max_height,
                    stats: lastOptimizationResult.stats
                })
            });
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'loading_plan.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }

        async function clearAllRequests() {
            if (!confirm('Are you sure you want to clear all cargo requests?')) {
                return;
            }
            
            const response = await fetch('/api/requests/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            
            const result = await response.json();
            if (result.success) {
                alert(result.message);
                await loadRequests();
                document.getElementById('resultsSection').classList.add('hidden');
                lastOptimizationResult = null;
                lastAircraftConfig = null;
            }
        }

        // Loading Crew View Functions
        async function loadLoadingCrewPlan() {
            try {
                const response = await fetch('/api/latest-plan');
                
                if (response.ok) {
                    const plan = await response.json();
                    displayLoadingCrewPlan(plan);
                } else {
                    showNoPlanMessage();
                }
            } catch (error) {
                console.error('Error loading plan:', error);
                showNoPlanMessage();
            }
        }

        function showNoPlanMessage() {
            document.getElementById('noPlanMessage').classList.remove('hidden');
            document.getElementById('planContent').classList.add('hidden');
        }

        function displayLoadingCrewPlan(plan) {
            document.getElementById('noPlanMessage').classList.add('hidden');
            document.getElementById('planContent').classList.remove('hidden');
            
            // Render the 4 PDF slices visually
            renderPDFSlices(plan);
            
            // Store plan for PDF download
            lastOptimizationResult = plan;
            lastAircraftConfig = {
                max_weight: plan.stats.max_weight,
                max_length: plan.aircraft.max_length,
                max_width: plan.aircraft.max_width,
                max_height: plan.aircraft.max_height
            };
        }

        function renderPDFSlices(plan) {
            const container = document.getElementById('pdfSlices');
            container.innerHTML = '';
            
            const maxLength = plan.aircraft.max_length;
            const maxWidth = plan.aircraft.max_width;
            const maxHeight = plan.aircraft.max_height;
            const quarterWidth = maxLength / 4;
            
            // Create 4 slices
            for (let quarter = 0; quarter < 4; quarter++) {
                const sliceStart = quarter * quarterWidth;
                const sliceEnd = (quarter + 1) * quarterWidth;
                
                // Filter items in this slice
                const itemsInSlice = plan.packed.filter(item => {
                    const itemX = item.position.x;
                    const itemLength = item.length;
                    const itemStart = itemX - itemLength/2;
                    const itemEnd = itemX + itemLength/2;
                    return itemStart < sliceEnd && itemEnd > sliceStart;
                });
                
                // Create slice container
                const sliceDiv = document.createElement('div');
                sliceDiv.className = 'bg-white border-2 border-gray-300 rounded-lg p-4';
                
                const title = document.createElement('h3');
                title.className = 'font-bold text-lg mb-3';
                title.style.color = '#5B6466';
                title.textContent = `Slice ${quarter + 1} of 4 (${sliceStart.toFixed(1)}m - ${sliceEnd.toFixed(1)}m)`;
                sliceDiv.appendChild(title);
                
                // Create canvas for visualization
                const canvas = document.createElement('canvas');
                canvas.width = 800;
                canvas.height = 600;
                canvas.className = 'w-full border border-gray-200 rounded';
                sliceDiv.appendChild(canvas);
                
                // Draw the slice
                drawSlice(canvas, itemsInSlice, maxWidth, maxHeight, plan.stats);
                
                container.appendChild(sliceDiv);
            }
        }

        function drawSlice(canvas, items, maxWidth, maxHeight, stats) {
            const ctx = canvas.getContext('2d');
            const padding = 50;
            const drawWidth = canvas.width - 2 * padding;
            const drawHeight = canvas.height - 2 * padding;
            
            // Clear canvas
            ctx.fillStyle = '#F9FAFB';
            ctx.fillRect(0, 0, canvas.width, canvas.height);
            
            // Draw title info
            ctx.fillStyle = '#5B6466';
            ctx.font = 'bold 16px Arial';
            ctx.fillText(`UH-60 Black Hawk - Top View`, padding, 30);
            
            ctx.font = '12px Arial';
            ctx.fillStyle = '#6B7280';
            ctx.fillText(`Weight: ${stats.total_weight.toFixed(1)}/${stats.max_weight} kg | Balance: ${stats.balance_score}%`, padding, canvas.height - 20);
            
            // Scale factors
            const scaleW = drawWidth / maxWidth;
            const scaleH = drawHeight / maxHeight;
            
            // Draw cargo bay outline
            ctx.strokeStyle = '#1F2937';
            ctx.lineWidth = 3;
            ctx.strokeRect(padding, padding, drawWidth, drawHeight);
            
            // Draw grid
            ctx.strokeStyle = '#D1D5DB';
            ctx.lineWidth = 1;
            for (let i = 0; i <= maxWidth; i += 0.5) {
                const x = padding + i * scaleW;
                ctx.beginPath();
                ctx.moveTo(x, padding);
                ctx.lineTo(x, padding + drawHeight);
                ctx.stroke();
            }
            for (let i = 0; i <= maxHeight; i += 0.5) {
                const y = padding + i * scaleH;
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(padding + drawWidth, y);
                ctx.stroke();
            }
            
            // Item type to color mapping
            const itemColors = {
                'Water Case (24 bottles)': 'rgb(51, 128, 230)',      // Blue
                'Dozen NP Food Cans': 'rgb(204, 77, 26)',            // Orange/Brown
                'First-Aid Kit': 'rgb(230, 26, 26)',                 // Red
                'Toilet Paper (12-Roll Pack)': 'rgb(242, 242, 242)', // White
                'Sanitary Pads (20 Pack)': 'rgb(230, 128, 204)',     // Pink
                'Clothing Pack (Jacket + Undergarments)': 'rgb(77, 77, 153)', // Dark Blue
                'Blanket (Rolled)': 'rgb(153, 102, 51)',             // Brown
                'Pet Supplies Pack': 'rgb(230, 179, 51)',            // Yellow
                'Baby Formula (Case)': 'rgb(204, 230, 179)'          // Light Green
            };
            
            items.forEach((item, idx) => {
                const posY = item.position.y;
                const posZ = item.position.z;
                const itemWidth = item.width;
                const itemHeight = item.height;
                
                const x = padding + (posY - itemWidth/2) * scaleW;
                // Flip Z axis - subtract from max to invert
                const y = padding + drawHeight - ((posZ + itemHeight/2) * scaleH);
                const w = itemWidth * scaleW;
                const h = itemHeight * scaleH;
                
                // Draw box with item type color
                ctx.fillStyle = itemColors[item.item_type] || 'rgb(128, 128, 204)'; // Default to gray-blue
                ctx.fillRect(x, y, w, h);
                
                ctx.strokeStyle = '#000';
                ctx.lineWidth = 2;
                ctx.strokeRect(x, y, w, h);
                
                // Draw label
                ctx.fillStyle = '#FFF';
                ctx.font = 'bold 12px Arial';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(`ID${item.id}`, x + w/2, y + h/2 - 8);
                
                ctx.font = '10px Arial';
                ctx.fillText(`${item.weight}kg`, x + w/2, y + h/2 + 6);
            });
            
            ctx.textAlign = 'left';
        }

        function refreshLoadingCrewView() {
            loadLoadingCrewPlan();
        }

        async function downloadLoadingCrewPDF() {
            if (!lastOptimizationResult || !lastAircraftConfig) {
                alert('No load plan available to download');
                return;
            }
            
            const response = await fetch('/api/export-pdf', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    packed: lastOptimizationResult.packed,
                    max_length: lastAircraftConfig.max_length,
                    max_width: lastAircraftConfig.max_width,
                    max_height: lastAircraftConfig.max_height,
                    stats: lastOptimizationResult.stats
                })
            });
            
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'loading_plan.pdf';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        }

        init();
    </script>
</body>
</html>
'''

if __name__ == '__main__':
    app.run(debug=True, port=5000)