from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Configure app
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure email
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Models
class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'message': self.message,
            'created_at': self.created_at.isoformat()
        }

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'lead_id': self.lead_id,
            'booking_date': self.booking_date.isoformat(),
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

# Helper functions
def send_confirmation_email(lead, booking=None):
    msg = Message(
        'Thank you for contacting Rami Marketing',
        sender=app.config['MAIL_USERNAME'],
        recipients=[lead.email]
    )
    
    if booking:
        msg.body = f"""
        Dear {lead.name},

        Thank you for scheduling a strategy call with Rami Marketing. 
        Your call is scheduled for {booking.booking_date}.

        We look forward to discussing how we can help transform your social media presence.

        Best regards,
        Rami Marketing Team
        """
    else:
        msg.body = f"""
        Dear {lead.name},

        Thank you for your interest in Rami Marketing. 
        We have received your message and will get back to you shortly.

        Best regards,
        Rami Marketing Team
        """
    
    mail.send(msg)

def send_admin_notification(lead, booking=None):
    msg = Message(
        'New Lead/Booking Alert',
        sender=app.config['MAIL_USERNAME'],
        recipients=[app.config['MAIL_USERNAME']]  # Send to admin email
    )
    
    if booking:
        msg.body = f"""
        New booking received:
        Name: {lead.name}
        Email: {lead.email}
        Booking Date: {booking.booking_date}
        Message: {lead.message}
        """
    else:
        msg.body = f"""
        New lead received:
        Name: {lead.name}
        Email: {lead.email}
        Message: {lead.message}
        """
    
    mail.send(msg)

# Routes
@app.route('/api/contact', methods=['POST'])
@limiter.limit("5 per minute")
def contact():
    try:
        data = request.json
        
        # Validate required fields
        if not all(k in data for k in ['name', 'email']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Create new lead
        lead = Lead(
            name=data['name'],
            email=data['email'],
            message=data.get('message', '')
        )
        db.session.add(lead)
        db.session.commit()
        
        # Send confirmation email
        try:
            send_confirmation_email(lead)
            send_admin_notification(lead)
        except Exception as e:
            print(f"Error sending email: {e}")
        
        return jsonify({'message': 'Contact form submitted successfully', 'lead': lead.to_dict()}), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/book', methods=['POST'])
@limiter.limit("3 per minute")
def book():
    try:
        data = request.json
        
        # Validate required fields
        if not all(k in data for k in ['name', 'email', 'booking_date']):
            return jsonify({'error': 'Missing required fields'}), 400
        
        # Create new lead and booking
        lead = Lead(
            name=data['name'],
            email=data['email'],
            message=data.get('message', '')
        )
        db.session.add(lead)
        db.session.flush()  # Get lead ID before committing
        
        booking_date = datetime.fromisoformat(data['booking_date'].replace('Z', '+00:00'))
        booking = Booking(
            lead_id=lead.id,
            booking_date=booking_date
        )
        db.session.add(booking)
        db.session.commit()
        
        # Send confirmation email
        try:
            send_confirmation_email(lead, booking)
            send_admin_notification(lead, booking)
        except Exception as e:
            print(f"Error sending email: {e}")
        
        return jsonify({
            'message': 'Booking submitted successfully',
            'booking': booking.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/available-slots', methods=['GET'])
def get_available_slots():
    # In a real application, this would check a calendar or booking system
    # For now, return some dummy available slots
    available_slots = [
        {
            'date': '2024-03-25',
            'slots': ['10:00', '14:00', '16:00']
        },
        {
            'date': '2024-03-26',
            'slots': ['09:00', '11:00', '15:00']
        },
        {
            'date': '2024-03-27',
            'slots': ['13:00', '14:00', '17:00']
        }
    ]
    return jsonify(available_slots)

# Error handlers
@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(port=5000, debug=True)