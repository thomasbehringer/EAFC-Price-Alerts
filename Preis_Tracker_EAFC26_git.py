import cloudscraper
import csv
import time
from datetime import datetime, timedelta, timezone
import os
import requests
from dateutil import parser
from dateutil.tz import tzutc


class FUTPlayerPriceTracker:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.domain = "https://www.fut.gg/api/fut/player-prices"
        self.version = 26
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.fut.gg/",
        }
        
    def get_player_price(self, player_id, player_name="Unknown"):
        url = f"{self.domain}/{self.version}/{player_id}/"
        
        try:
            response = self.scraper.get(url, headers=self.headers)
            
            if response.status_code == 200:
                data = response.json()
                
                average_bin = data["data"]["overview"].get("averageBin", None)
                
                lowest_bid_info = self.extract_lowest_bid(data.get("data", {}).get("liveAuctions", []))
                
                is_extinct = data['data']['currentPrice'].get('isExtinct', False)
                
                if is_extinct:
                    print(f"⚠️ {player_name}: EXTINCT - Keine Marktangebote verfügbar")
                    
                    return {
                        'player_id': player_id,
                        'player_name': player_name,
                        'current_price': 'EXTINCT',
                        'last_bin': 'EXTINCT',
                        'average_bin': average_bin,
                        'lowest_bid': lowest_bid_info['lowest_bid'],
                        'lowest_bid_expires_in': lowest_bid_info['expires_in'],
                        'lowest_bid_end_time': lowest_bid_info['end_time'],
                        'seconds_remaining': lowest_bid_info['seconds_remaining'],
                        'price_updated_at': data['data']['currentPrice'].get('priceUpdatedAt', ''),
                        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                else:
                    current_price = data['data']['currentPrice']['price']
                    price_updated_at = data['data']['currentPrice']['priceUpdatedAt']
                    
                    last_bin = None
                    if data['data']['momentum'].get('lastUpdates'):
                        last_bin = data['data']['momentum']['lastUpdates'][0]['bin']
                    
                    avg_bin_display = f"{average_bin:,}" if average_bin else "N/A"
                    last_bin_display = f"{last_bin:,}" if last_bin else "N/A"
                    bid_display = f"{lowest_bid_info['lowest_bid']:,}" if lowest_bid_info['lowest_bid'] else "N/A"
                    expires_display = lowest_bid_info['expires_in'] if lowest_bid_info['expires_in'] else "N/A"
                    
                    print(f"✓ {player_name}: Aktueller Preis = {current_price:,} coins")
                    print(f"  └─ Letzter BIN: {last_bin_display}, Durchschnitt BIN: {avg_bin_display}")
                    print(f"  └─ Niedrigstes Gebot: {bid_display} (läuft ab in: {expires_display})")
                    
                    return {
                        'player_id': player_id,
                        'player_name': player_name,
                        'current_price': current_price,
                        'last_bin': last_bin,
                        'average_bin': average_bin,
                        'lowest_bid': lowest_bid_info['lowest_bid'],
                        'lowest_bid_expires_in': lowest_bid_info['expires_in'],
                        'lowest_bid_end_time': lowest_bid_info['end_time'],
                        'seconds_remaining': lowest_bid_info['seconds_remaining'],
                        'price_updated_at': price_updated_at,
                        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
            else:
                print(f"✗ Fehler beim Abrufen von {player_name} (ID: {player_id}) - Status: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"✗ Fehler beim Abrufen von {player_name}: {str(e)}")
            return None
    
    def extract_lowest_bid(self, live_auctions):
        if not live_auctions:
            return {'lowest_bid': None, 'expires_in': None, 'end_time': None, 'seconds_remaining': None}
        
        try:
            lowest_auction = min(live_auctions, key=lambda x: x.get('startingBid', float('inf')))
            lowest_bid = lowest_auction.get('startingBid')
            end_date_str = lowest_auction.get('endDate')
            
            if end_date_str and lowest_bid is not None:
                end_date = parser.parse(end_date_str)
                
                now = datetime.now(timezone.utc)
                
                if end_date.tzinfo is None:
                    end_date = end_date.replace(tzinfo=timezone.utc)
                
                time_diff = end_date - now
                total_seconds = time_diff.total_seconds()
                
                if total_seconds > 0:
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    seconds = int(total_seconds % 60)
                    
                    if hours > 0:
                        expires_in = f"{hours}h {minutes}m"
                    elif minutes > 0:
                        expires_in = f"{minutes}m {seconds}s"
                    else:
                        expires_in = f"{seconds}s"
                else:
                    expires_in = "Abgelaufen"
                    total_seconds = 0
                
                return {
                    'lowest_bid': lowest_bid,
                    'expires_in': expires_in,
                    'end_time': end_date.strftime('%Y-%m-%d %H:%M:%S UTC'),
                    'seconds_remaining': total_seconds
                }
            
            return {'lowest_bid': lowest_bid, 'expires_in': None, 'end_time': None, 'seconds_remaining': None}
            
        except Exception as e:
            print(f"  └─ Fehler beim Extrahieren der Gebotsdaten: {str(e)}")
            return {'lowest_bid': None, 'expires_in': None, 'end_time': None, 'seconds_remaining': None}
    
    def track_multiple_players(self, players_dict, delay_between_requests=1):
        results = []
        
        print(f"\n{'='*60}")
        print(f"Rufe Preise für {len(players_dict)} Spieler ab...")
        print(f"{'='*60}\n")
        
        for player_name, player_id in players_dict.items():
            price_data = self.get_player_price(player_id, player_name)
            if price_data:
                results.append(price_data)
            
            if delay_between_requests > 0:
                time.sleep(delay_between_requests)
        
        return results
    
    def save_to_csv(self, price_data, filename="fut_player_prices.csv", mode='w'):
        """
        Save price data to CSV file
        mode='w' overwrites the file, mode='a' appends to existing file
        """
        if not price_data:
            print("Keine Daten zum Speichern!")
            return
        
        file_exists = os.path.exists(filename)
        
        try:
            with open(filename, mode, newline='', encoding='utf-8') as csvfile:
                fieldnames = ['fetch_time', 'player_id', 'player_name', 'current_price', 'last_bin', 
                             'average_bin', 'lowest_bid', 'lowest_bid_expires_in', 'lowest_bid_end_time', 
                             'seconds_remaining', 'price_updated_at']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                if mode == 'w' or not file_exists:
                    writer.writeheader()
                
                writer.writerows(price_data)
            
            print(f"\n✓ Daten nach {filename} geschrieben")
            print(f"  Modus: {'Überschreiben' if mode == 'w' else 'Anhängen'}")
            print(f"  Gespeicherte Einträge: {len(price_data)}")
            
        except PermissionError:
            print(f"\n✗ Zugriff verweigert: Kann nicht nach '{filename}' schreiben")
            print("  Mögliche Lösungen:")
            print("  1. Schließe die Datei, wenn sie in Excel oder einem anderen Programm geöffnet ist")
            print("  2. Überprüfe, ob die Datei schreibgeschützt ist")
            print("  3. Versuche in einen anderen Ordner zu speichern")
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            alt_filename = f"fut_prices_{timestamp}.csv"
            print(f"\n  Versuche alternative Datei: {alt_filename}")
            
            try:
                with open(alt_filename, mode, newline='', encoding='utf-8') as csvfile:
                    fieldnames = ['fetch_time', 'player_id', 'player_name', 'current_price', 'last_bin', 
                                 'average_bin', 'lowest_bid', 'lowest_bid_expires_in', 'lowest_bid_end_time', 
                                 'seconds_remaining', 'price_updated_at']
                    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                    
                    if mode == 'w' or not os.path.exists(alt_filename):
                        writer.writeheader()
                    
                    writer.writerows(price_data)
                
                print(f"  ✓ Erfolgreich nach {alt_filename} gespeichert")
                
            except Exception as e2:
                print(f"  ✗ Alternative Datei konnte auch nicht gespeichert werden: {str(e2)}")
                
        except Exception as e:
            print(f"\n✗ Fehler beim Speichern der CSV: {str(e)}")

class PriceAlert:
    def __init__(self, webhook_url=None):
        self.webhook_url = webhook_url
    
    def check_price(self, player_data):
        """Check for BIN price drops"""
        current_price = player_data['current_price']
        average_bin = player_data.get('average_bin')
        
        if current_price == 'EXTINCT' or average_bin is None:
            return False

        if average_bin > 0 and current_price <= average_bin * 0.75:
            print(
                f"📉 BIN-Preissturz! {player_data['player_name']} ist unter Durchschnitt gefallen: "
                f"Durchschnitt BIN {average_bin:,} → Aktuell {current_price:,} Coins "
                f"({((average_bin - current_price) / average_bin * 100):.1f}% Rabatt)"
            )
            self.send_alert(
                player_data,
                alert_type="BIN",
                reason=f"> 25%+ unter Durchschnitt BIN ({average_bin:,} Coins)"
            )
            return True
        
        return False
    
    def check_bidding_opportunity(self, player_data):
        """Check for bidding opportunities"""
        current_price = player_data['current_price']
        lowest_bid = player_data.get('lowest_bid')
        expires_in = player_data.get('lowest_bid_expires_in')
        seconds_remaining = player_data.get('seconds_remaining')
        
        if current_price == 'EXTINCT' or lowest_bid is None:
            return False
        
        if current_price > 0 and lowest_bid <= current_price * 0.5 and seconds_remaining < 120 and expires_in != "Abgelaufen":
            discount_percent = ((current_price - lowest_bid) / current_price * 100)
            print(
                f"🎯 Gebotschance! {player_data['player_name']}: "
                f"Niedrigstes Gebot {lowest_bid:,} vs. BIN {current_price:,} Coins "
                f"({discount_percent:.1f}% günstiger) - Läuft ab in: {expires_in}"
            )
            self.send_alert(
                player_data,
                alert_type="BIDDING",
                reason=f"Gebot {discount_percent:.1f}% unter BIN-Preis! Läuft ab in: {expires_in}"
            )
            return True
        
        return False
    
    def send_alert(self, player_data, alert_type="BIN", reason=""):
        if not self.webhook_url:
            print("⚠️ Kein Webhook-URL angegeben, Nachricht nicht gesendet.")
            return
        
        if alert_type == "BIN":
            discount_text = ""
            if player_data.get('average_bin') and player_data['current_price'] != 'EXTINCT':
                discount = (player_data['average_bin'] - player_data['current_price']) / player_data['average_bin'] * 100
                discount_text = f"**{discount:.1f}% Rabatt!**\n"
            
            message = {
                "content": (
                    f"🔔 **BIN-Preisalarm!**\n"
                    f"{player_data['player_name']} ist jetzt für **{player_data['current_price']:,} Coins** verfügbar!\n"
                    f"{discount_text}"
                    f"{reason}\n"
                    f"Zeit: {player_data['fetch_time']}"
                )
            }
        else:  
            message = {
                "content": (
                    f"🎯 **⏰ LAST-MINUTE Gebotschance!**\n"
                    f"{player_data['player_name']}\n"
                    f"Niedrigstes Gebot: **{player_data['lowest_bid']:,} Coins**\n"
                    f"BIN-Preis: **{player_data['current_price']:,} Coins**\n"
                    f"{reason}\n"
                    f"Zeit: {player_data['fetch_time']}"
                )
            }
        
        try:
            response = requests.post(self.webhook_url, json=message)
            if response.status_code == 204:
                print(f"✓ Discord-{alert_type}-Alarm erfolgreich gesendet!")
            else:
                print(
                    f"✗ Fehler beim Senden der {alert_type}-Nachricht - "
                    f"Status: {response.status_code} - {response.text}"
                )
        except Exception as e:
            print(f"❌ Fehler beim Senden an Discord: {e}")


if __name__ == "__main__":
    tracker = FUTPlayerPriceTracker()
    alert = PriceAlert(webhook_url="YOUR_DISCORD_WEBHOOK_URL_HERE")

    while True:
        gold_players = {
            "Kylian Mbappe": 231747,
            "Ousmane Dembele": 231443,
            "Graham Hansen": 227102,
            "Erling Haaland": 239085,
            "Alexia Putellas": 227203,
            "Jamal Musiala": 256790,
            "Mohammed Salah": 209331,
            "Aitana Bonmati": 241667,
            "Jude Bellingham": 252371,
            "Virgil van Dijk": 203376,
            "Lamine Yamal": 277643,
            "Achraf Hakimi": 235212,
            "Micky Van De Ven": 264453, 
            "Tijjani Reijnders": 240638,
            "Viktor Gyoekeres": 241651,
            "Alexander Isak": 50565379
        }
        
        results = tracker.track_multiple_players(gold_players, delay_between_requests=1)
        tracker.save_to_csv(results, "gold_spieler_preise.csv", mode='w')
        
        for player_data in results:
            alert.check_price(player_data)
            alert.check_bidding_opportunity(player_data)

        icons = {
            "R9": 37576, 
            "Eusebio": 242519,
            "Pele": 237067,
            "Garrincha": 247553,
            "Ronaldinho": 28130,
            "Patrick Vieira": 238427,
            "Paolo Maldini": 238439,
            "Sir Bobby Charlton": 230025,
            "Zinedine Zidane": 1397,
            "Mia Hamm": 275243,
            "Johann Cruyff": 190045,
            "Thierry Henry": 1625,
            "Marcel Desailly": 1116,
            "Kenny Dalglish": 247699,
            "Ruud Gullit": 214100,
            "Oliver Kahn": 488,
        }

        results_icons = tracker.track_multiple_players(icons, delay_between_requests=1)
        tracker.save_to_csv(results_icons, "icons_preise.csv", mode='w')
        
        for player_data in results_icons:
            alert.check_price(player_data)
            alert.check_bidding_opportunity(player_data)

        heroes = {
            "David Ginola": 191972,
            "Yaya Toure": 20289,
            "Lucio": 266690,
            "Ramires": 184943,
            "Eden Hazard": 183277, 
            "Jaap Stam": 5740,
            "Rudi Voeller": 166676,
            "Abedi Pele": 167425,
            "David Capdevila": 25924,
            "Harry Kewell": 266801,
            "Wesley Sneijder": 274750,
            "Ivan Cordoba": 16619,
        }
        
        results_heroes = tracker.track_multiple_players(heroes, delay_between_requests=1)
        tracker.save_to_csv(results_heroes, "heroes_preise.csv", mode='w')
        
        for player_data in results_heroes:
            alert.check_price(player_data)
            alert.check_bidding_opportunity(player_data)

        now = datetime.now()
        next_run = now + timedelta(seconds=100)
        print(f"\nNächster Lauf um {next_run.strftime('%H:%M:%S')}")
        time.sleep(100)