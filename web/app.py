"""
Flask web uygulaması
Itinerary (rota) tabanlı seyahat planlama
"""
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
from agents.orchestrator import AgentOrchestrator
from models.data_models import UserPreferences
from utils.config import config
from utils.google_api import google_api


app = Flask(__name__)
CORS(app)

# Ajan orkestratörü
orchestrator = AgentOrchestrator()


@app.route('/')
def index():
    """Ana sayfa"""
    return render_template('index.html')


@app.route('/api/generate-plan', methods=['POST'])
def generate_plan():
    """Itinerary (günlük rota planı) oluştur"""
    try:
        data = request.get_json()
        print(f"📨 Gelen istek: {data}")
        
        user_preferences = UserPreferences(
            interests=data.get('interests', []),
            budget=float(data.get('budget', 5000)),
            start_date=datetime.fromisoformat(data.get('start_date')),
            end_date=datetime.fromisoformat(data.get('end_date')),
            location=data.get('location', ''),
            constraints=data.get('constraints', {})
        )
        
        result = orchestrator.generate_itinerary(user_preferences)
        
        if result['success']:
            itinerary = result['itinerary']
            
            # Itinerary'yi JSON'a çevir
            itinerary_dict = {
                'city': itinerary.city,
                'total_days': itinerary.total_days,
                'explanation': itinerary.explanation,
                'optimization_score': itinerary.optimization_score,
                'accommodation': None,
                'budget': {
                    'accommodation': itinerary.budget.accommodation,
                    'activities': itinerary.budget.activities,
                    'food': itinerary.budget.food,
                    'transport': itinerary.budget.transport,
                    'extras': itinerary.budget.extras,
                    'total': itinerary.budget.total,
                    'remaining': itinerary.budget.remaining,
                    'user_budget': itinerary.budget.user_budget,
                },
                'days': []
            }
            
            # Konaklama
            if itinerary.accommodation:
                acc = itinerary.accommodation
                itinerary_dict['accommodation'] = {
                    'name': acc.name,
                    'address': acc.address,
                    'rating': acc.rating,
                    'price_per_night': acc.price_per_night,
                    'total_nights': acc.total_nights,
                    'total_cost': acc.total_cost,
                    'photo_url': google_api.get_photo_url(acc.photo_ref) if acc.photo_ref else '',
                }
            
            # Günler
            for day in itinerary.days:
                day_dict = {
                    'day_number': day.day_number,
                    'date': day.date,
                    'day_total': day.day_total,
                    'activities_cost': day.activities_cost,
                    'meals_cost': day.meals_cost,
                    'transport_cost': day.transport_cost,
                    'places': [],
                    'transport_legs': []
                }
                
                for place in day.places:
                    day_dict['places'].append({
                        'name': place.name,
                        'address': place.address,
                        'category': place.category,
                        'rating': place.rating,
                        'duration_minutes': place.duration_minutes,
                        'estimated_cost': place.estimated_cost,
                        'description': place.description,
                        'photo_url': google_api.get_photo_url(place.photo_ref) if place.photo_ref else '',
                        'lat': place.lat,
                        'lng': place.lng,
                    })
                
                for leg in day.transport_legs:
                    day_dict['transport_legs'].append({
                        'origin': leg.origin_name,
                        'destination': leg.destination_name,
                        'distance': leg.distance_text,
                        'duration': leg.duration_text,
                        'mode': leg.mode,
                    })
                
                itinerary_dict['days'].append(day_dict)
            
            return jsonify({
                'success': True,
                'itinerary': itinerary_dict,
                'message': result.get('message', 'Plan hazır!')
            })
        else:
            return jsonify({
                'success': False,
                'message': result.get('message', 'Plan oluşturulamadı')
            }), 400
    
    except Exception as e:
        import traceback
        print(f"❌ API Hatası: {str(e)}")
        print(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': f'Hata: {str(e)}'
        }), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Serbest sohbet - Llama LLM ile"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        history = data.get('history', [])
        
        from utils.llm_wrapper import llm_wrapper
        
        messages = [
            {
                "role": "system",
                "content": "Sen AR-VPlanner asistanısın. Seyahat, gezi ve genel konularda yardımcı bir yapay zeka asistanısın. Türkçe yanıt ver. Kısa ve öz cevaplar ver."
            }
        ]
        
        for msg in history[-10:]:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", "")
            })
        
        messages.append({"role": "user", "content": user_message})
        
        response_text = llm_wrapper.chat(messages=messages, max_tokens=256, temperature=0.7)
        
        return jsonify({'success': True, 'response': response_text})
    
    except Exception as e:
        import traceback
        print(f"❌ Sohbet hatası: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'response': f'Bir hata oluştu: {str(e)}'}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'healthy',
        'google_api': google_api.is_available,
        'service': 'AR-VPlanner Itinerary'
    })


if __name__ == '__main__':
    host = config.get('web.host', '0.0.0.0')
    port = config.get('web.port', 5000)
    debug = config.get('web.debug', True)
    app.run(host=host, port=port, debug=debug)
