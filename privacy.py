"""The privacy policy of the website and of the mobile app (pages /confidentialite and /en/privacy; the stores link to them).

One text, written once here, used by the crawler version of the page (seo.py), by the page itself (/api/privacy) and by the app's link.
It describes what the code actually does (traffic.py, mvp.py, predict.py, content.py, the app in mobile/): keep it true when that changes.
"""
UPDATED = "2026-11-20"
CONTACT = "https://www.facebook.com/people/Tunisia-Basket/61596371069928/"

TEXT = {
    "fr": {
        "title": "Politique de confidentialité",
        "intro": "Tunisia Basket (le site tunisiabasket.com et l’application mobile Tunisia Basket) publie les résultats et les statistiques du basket tunisien. "
                 "Nous n’avons pas de comptes utilisateurs, pas de publicité et pas de traceurs publicitaires. Voici exactement ce qui est enregistré, et pourquoi.",
        "sections": [
            ("Ce que nous ne collectons pas", [
                "Ni nom, ni adresse e-mail, ni numéro de téléphone, ni localisation précise, ni contacts, ni photos de votre appareil.",
                "Aucun cookie publicitaire ou de mesure d’audience tiers (pas de Google Analytics, pas de pixel Facebook). Nous ne vendons ni ne partageons aucune donnée.",
            ]),
            ("Statistiques de visite (site)", [
                "Pour savoir quelles pages sont lues, chaque page vue enregistre : le jour et l’heure, la page, le pays (donné par notre hébergeur), le site d’où vous venez, "
                "le type d’appareil (mobile, ordinateur…) et la langue.",
                "Pour compter les visiteurs sans les identifier, nous gardons deux codes : un code calculé chaque jour à partir de l’adresse IP et du navigateur avec une clé secrète "
                "(il change tous les jours et ne permet pas de retrouver l’adresse), et un code aléatoire que votre navigateur garde. Les adresses IP ne sont jamais enregistrées. "
                "Ces statistiques sont effacées au bout de 400 jours.",
            ]),
            ("Votes et pronostics", [
                "Quand vous votez (MVP, joueur de la journée) ou faites un pronostic, nous enregistrons votre choix avec un code aléatoire propre à votre appareil, "
                "et une empreinte chiffrée de votre réseau pour éviter les votes en double. Ni l’un ni l’autre ne permet de savoir qui vous êtes.",
            ]),
            ("Ce qui reste sur votre appareil", [
                "Le site et l’application gardent sur votre appareil vos préférences : la langue, le thème, votre club favori, la saison affichée, "
                "un identifiant aléatoire (pour les votes) et une copie des dernières données consultées pour fonctionner hors ligne. "
                "Vous pouvez tout effacer en vidant les données du navigateur ou en désinstallant l’application.",
                "Si vous choisissez un club favori, nous comptons combien de lecteurs suivent chaque club, sans rien enregistrer d’autre sur vous.",
            ]),
            ("Application mobile", [
                "L’application lit les mêmes données publiques que le site. Elle ne demande aucune autorisation particulière (ni localisation, ni appareil photo, ni contacts), "
                "ne contient pas de publicité et n’utilise aucun outil de suivi.",
            ]),
            ("Hébergeurs et liens externes", [
                "Le site passe par des prestataires techniques (hébergement, Cloudflare) qui traitent l’adresse IP le temps de vous envoyer les pages, selon leurs propres règles. "
                "Les liens vers Facebook, Instagram ou d’autres sites mènent à des services qui ont leur propre politique de confidentialité.",
            ]),
            ("Mineurs", [
                "Le service s’adresse à tous les publics et ne collecte sciemment aucune donnée personnelle, y compris d’enfants.",
            ]),
            ("Vos droits et contact", [
                "Comme nous ne gardons pas de données qui vous identifient, il n’y a en principe rien à consulter ou à supprimer de notre côté. "
                "Pour toute question, demande ou correction, écrivez-nous sur notre page Facebook.",
                "Nous pouvons modifier cette politique ; la date de mise à jour figure en haut de la page.",
            ]),
        ],
    },
    "en": {
        "title": "Privacy policy",
        "intro": "Tunisia Basket (the website tunisiabasket.com and the Tunisia Basket mobile app) publishes the results and statistics of Tunisian basketball. "
                 "There are no user accounts, no ads and no advertising trackers. Here is exactly what is recorded, and why.",
        "sections": [
            ("What we do not collect", [
                "No name, email address, phone number, precise location, contacts or photos from your device.",
                "No third-party advertising or analytics cookies (no Google Analytics, no Facebook pixel). We do not sell or share any data.",
            ]),
            ("Visit statistics (website)", [
                "To know which pages are read, each page view records: the day and time, the page, the country (given by our host), the site you came from, "
                "the device type (phone, computer…) and the language.",
                "To count visitors without identifying them we keep two codes: one computed each day from the IP address and the browser with a secret key "
                "(it changes every day and cannot be turned back into an address), and a random code your browser keeps. IP addresses are never stored. "
                "These statistics are deleted after 400 days.",
            ]),
            ("Votes and predictions", [
                "When you vote (MVP, player of the round) or make a prediction, we record your choice with a random code of your device, "
                "and an encrypted fingerprint of your network to prevent double votes. Neither tells us who you are.",
            ]),
            ("What stays on your device", [
                "The website and the app keep your preferences on your device: language, theme, favourite club, the season shown, "
                "a random identifier (for votes) and a copy of the latest data you viewed so they work offline. "
                "You can erase everything by clearing your browser data or uninstalling the app.",
                "If you pick a favourite club, we count how many readers follow each club, without recording anything else about you.",
            ]),
            ("Mobile app", [
                "The app reads the same public data as the website. It asks for no special permission (no location, camera or contacts), "
                "shows no ads and uses no tracking tools.",
            ]),
            ("Hosting and external links", [
                "The website goes through technical providers (hosting, Cloudflare) that process the IP address while delivering the pages, under their own rules. "
                "Links to Facebook, Instagram or other sites lead to services with their own privacy policies.",
            ]),
            ("Children", [
                "The service is for all audiences and does not knowingly collect personal data, including from children.",
            ]),
            ("Your rights and contact", [
                "As we keep no data that identifies you, there is normally nothing for us to show or delete. "
                "For any question, request or correction, write to us on our Facebook page.",
                "We may change this policy; the date of the last update is shown at the top of the page.",
            ]),
        ],
    },
}


def view(lang):
    t = TEXT.get(lang) or TEXT["fr"]
    return {"lang": lang if lang in TEXT else "fr", "updated": UPDATED, "contact": CONTACT, "title": t["title"], "intro": t["intro"],
            "sections": [{"h": h, "p": ps} for h, ps in t["sections"]]}
