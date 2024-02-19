###### Détection_Tracking_Véhicules

Je suis enthousiaste à l'idée de vous présenter le fonctionnement de mon projet de fin d'études réalisé en 2022. 
Ce projet a été conçu pour lutter contre la fraude aux péages sur les autoroutes marocaines, en développant un système intelligent capable de détecter et de classifier différents types de véhicules. Le système est conçu pour fonctionner en temps réel, identifiant les véhicules qui évitent de payer le péage.

Au cours du projet, nous nous sommes engagés à préparer des images de diverses catégories, en utilisant des techniques d'augmentation de données pour enrichir notre base de données. Par la suite, nous avons formé plusieurs modèles, y compris les ResNets, différentes versions de YOLO, les familles de RCNN, SSD, et avons sélectionné le meilleur algorithme répondant à nos besoins, en fonction de la vitesse de détection, de la précision et de la performance en temps réel sur les vidéos.

Pour suivre les objets à travers les images et prévenir la répétition des objets, nous avons implémenté des algorithmes de suivi, en intégrant spécifiquement un modèle de filtre de Kalman pour le suivi.

Pour déployer ce projet sur votre système, je vous invite à installer les bibliothèques listées dans les fichiers 'requirements.txt' et 'requirements-gpu.txt', puis à exécuter le script 'object_tracker.py'.

Pour ceux qui sont intéressés à approfondir les aspects théoriques et pratiques de ce projet, je vous encourage à lire attentivement le rapport et la présentation disponibles dans le dépôt.





