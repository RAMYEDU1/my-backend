from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from datetime import datetime
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Mailgun Configuration
app.config['MAIL_SERVER'] = os.getenv('MAILGUN_SMTP_SERVER', 'smtp.mailgun.org')
app.config['MAIL_PORT'] = int(os.getenv('MAILGUN_SMTP_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAILGUN_SMTP_LOGIN')
app.config['MAIL_PASSWORD'] = os.getenv('MAILGUN_SMTP_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAILGUN_SENDER_EMAIL')

# Initialize Flask-Mail
mail = Mail(app)

# Configure Database - Render provides PostgreSQL
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

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

# Routes
@app.route('/api/contact', methods=['POST'])
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

        # Send email notification
        try:
            msg = Message(
                subject='New Contact Form Submission',
                recipients=[app.config['MAIL_DEFAULT_SENDER']],
                body=f"""
                New contact form submission:
                
                Name: {lead.name}
                Email: {lead.email}
                Message: {lead.message}
                
                Submitted at: {lead.created_at}
                """
            )
            mail.send(msg)
        except Exception as e:
            print(f"Email sending failed: {str(e)}")
            # Continue even if email fails
        
        return jsonify({
            'message': 'Contact form submitted successfully',
            'lead': lead.to_dict()
        }), 201
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Health check endpoint for Render
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy'}), 200

# Create database tables
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port)