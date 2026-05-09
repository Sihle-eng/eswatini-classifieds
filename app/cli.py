# File: app/cli.py

import click
from flask.cli import with_appcontext
from datetime import datetime, timedelta
from app import db
from app.models import Posting, User
from app.email_utils import send_ad_expiry_reminder

@click.command('check-expiring-ads')
@with_appcontext
def check_expiring_ads_command():
    """Check for ads expiring in 2 days and send reminder emails."""
    
    two_days_from_now = datetime.utcnow() + timedelta(days=2)
    tomorrow = datetime.utcnow() + timedelta(days=1)
    
    # Get ads expiring in exactly 2 days (between 24h and 48h from now)
    expiring_soon = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at > tomorrow,
        Posting.expires_at <= two_days_from_now
    ).all()
    
    count = 0
    for ad in expiring_soon:
        business_user = User.query.get(ad.business.user_id)
        if business_user:
            try:
                send_ad_expiry_reminder(
                    business_user.email,
                    ad.title,
                    ad.expires_at,
                    ad.id
                )
                count += 1
                click.echo(f"✓ Sent reminder for Ad #{ad.id} to {business_user.email}")
            except Exception as e:
                click.echo(f"✗ Failed for Ad #{ad.id}: {e}")
    
    click.echo(f"\n✅ Completed! Sent {count} expiry reminders.")

@click.command('deactivate-expired-ads')
@with_appcontext
def deactivate_expired_ads_command():
    """Deactivate ads that have passed their expiration date."""
    
    now = datetime.utcnow()
    
    expired_ads = Posting.query.filter(
        Posting.is_active == True,
        Posting.expires_at < now
    ).all()
    
    count = 0
    for ad in expired_ads:
        ad.is_active = False
        count += 1
        click.echo(f"✓ Deactivated Ad #{ad.id}: {ad.title[:30]}...")
    
    db.session.commit()
    click.echo(f"\n✅ Completed! Deactivated {count} expired ads.")

@click.command('send-daily-digest')
@with_appcontext
def send_daily_digest_command():
    """Send daily digest email to clients with new ads in their preferred categories."""
    
    # Get all client users
    clients = User.query.filter_by(user_type='client').all()
    
    count = 0
    for client in clients:
        if client.client_profile and client.client_profile.preferred_city:
            # Get new ads from last 24 hours in preferred city
            yesterday = datetime.utcnow() - timedelta(days=1)
            new_ads = Posting.query.filter(
                Posting.is_active == True,
                Posting.created_at > yesterday,
                Posting.location_city == client.client_profile.preferred_city
            ).limit(5).all()
            
            if new_ads:
                # In a real implementation, send email here
                count += 1
                click.echo(f"✓ Would send digest to {client.email} with {len(new_ads)} new ads")
    
    click.echo(f"\n✅ Completed! Would send {count} daily digests.")

# Register all commands
def register_commands(app):
    app.cli.add_command(check_expiring_ads_command)
    app.cli.add_command(deactivate_expired_ads_command)
    app.cli.add_command(send_daily_digest_command)