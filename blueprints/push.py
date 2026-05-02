import os
import json
from flask import Blueprint, request, jsonify
from flask_login import current_user, login_required
from extensions import db
from models import PushSubscription
from pywebpush import webpush, WebPushException

push_bp = Blueprint('push', __name__)

VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY')
VAPID_CLAIM_EMAIL = os.environ.get('VAPID_CLAIM_EMAIL', 'mailto:admin@example.com')

@push_bp.route('/push-key', methods=['GET'])
def get_push_key():
    return jsonify({'public_key': VAPID_PUBLIC_KEY})

@push_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    subscription_data = request.get_json()
    if not subscription_data:
        return jsonify({'error': 'No subscription data'}), 400

    # 기존 구독 확인
    existing = PushSubscription.query.filter_by(
        user_id=current_user.id, 
        endpoint=subscription_data['endpoint']
    ).first()
    
    if existing:
        return jsonify({'status': 'already subscribed'})

    new_subscription = PushSubscription(
        user_id=current_user.id,
        endpoint=subscription_data['endpoint'],
        p256dh=subscription_data['keys']['p256dh'],
        auth=subscription_data['keys']['auth']
    )
    db.session.add(new_subscription)
    db.session.commit()
    
    return jsonify({'status': 'success'})

@push_bp.route('/unsubscribe', methods=['POST'])
@login_required
def unsubscribe():
    subscription_data = request.get_json()
    if not subscription_data:
        return jsonify({'error': 'No subscription data'}), 400

    subscription = PushSubscription.query.filter_by(
        user_id=current_user.id,
        endpoint=subscription_data['endpoint']
    ).first()
    
    if subscription:
        db.session.delete(subscription)
        db.session.commit()
        return jsonify({'status': 'success'})
    
    return jsonify({'status': 'not found'}), 404

def send_push_to_user(user, title, body, url='/'):
    subscriptions = PushSubscription.query.filter_by(user_id=user.id).all()
    results = []
    
    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {
                        "p256dh": sub.p256dh,
                        "auth": sub.auth
                    }
                },
                data=json.dumps({
                    "title": title,
                    "body": body,
                    "url": url
                }),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={
                    "sub": VAPID_CLAIM_EMAIL
                }
            )
            results.append(True)
        except WebPushException as ex:
            print(f"Push failed: {ex}")
            # 구독이 만료되었거나 유효하지 않은 경우 삭제
            if ex.response and ex.response.status_code in [404, 410]:
                db.session.delete(sub)
                db.session.commit()
            results.append(False)
    return results
