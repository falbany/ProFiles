# Guide: Serveur Réseau ProFiles

**Version** : 1.0  
**Date** : 2026-10-15  
**Fonctionnalité** : Partage réseau local - Accès depuis d'autres PC

---

## 📖 Introduction

Ce guide explique comment rendre ProFiles accessible depuis d'autres PC de votre réseau local, permettant à vos collègues ou autres machines d'accéder aux fichiers hébergés sur votre PC.

---

## 🎯 Prérequis

### Configuration Système

- **PC Hôte** : Windows avec ProFiles installé
- **PC Clients** : N'importe quel PC avec un navigateur web moderne
- **Réseau** : Tous les PC doivent être sur le même réseau local (même sous-réseau)

### Vérifications

1. **Même réseau** : Vérifiez que tous les PC sont sur le même réseau (ex: 192.168.1.x)
2. **Firewall** : Le pare-feu Windows doit être configuré pour autoriser le port 8088
3. **ProFiles installé** : Le PC hôte doit avoir ProFiles installé et fonctionnel

---

## 🚀 Configuration du PC Hôte

### Étape 1: Autoriser le port dans le Firewall

Ouvrez PowerShell en **administrateur** et exécutez :

```powershell
New-NetFirewallRule -DisplayName "ProFiles Server" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow
```

**Alternative via l'interface graphique** :

1. Ouvrez "Pare-feu Windows Defender avec sécurité avancée"
2. Cliquez sur "Règles de trafic entrant"
3. "Nouvelle règle..." → "Port" → "TCP" → "8088"
4. "Autoriser la connexion"
5. Nommez-la "ProFiles Server"

### Étape 2: Démarrer le serveur

Dans un terminal, exécutez :

```powershell
ProFiles --server-only
```

**Sortie attendue** :

```
ProFiles server running at:
  Local:  http://127.0.0.1:8088
  Network: http://192.168.1.100:8088
  Access from other PCs on your network (press Ctrl+C to stop)
```

**Note importante** : Notez l'adresse **Network** (ex: `192.168.1.100:8088`) - c'est l'URL que les autres PC utiliseront.

### Étape 3: Vérifier que le serveur fonctionne

Ouvrez votre navigateur sur le PC hôte et accédez à :

```
http://127.0.0.1:8088
```

Vous devriez voir l'interface ProFiles.

---

## 💻 Accès depuis les PC Clients

### Étape 1: Ouvrir le navigateur

Sur un PC client (dans le même réseau), ouvrez n'importe quel navigateur moderne :

- Chrome, Edge, Firefox, Safari

### Étape 2: Accéder à l'URL du serveur

Dans la barre d'adresse, tapez l'URL affichée sur le PC hôte :

```
http://192.168.1.100:8088
```

**Remplacez** `192.168.1.100` par l'IP réelle affichée sur le PC hôte.

### Étape 3: Utiliser l'interface

L'interface ProFiles s'affiche exactement comme sur le PC hôte :

- ✅ **Scan des fichiers** : Cliquez sur "Scan" pour lister les fichiers
- ✅ **Filtrage** : Filtrez par extension (.txt, .py, etc.)
- ✅ **Lancement** : Cliquez sur un fichier pour le lancer **sur le PC hôte**
- ✅ **Configuration** : Chargez des configurations personnalisées

**Important** : Les fichiers sont lancés sur le **PC hôte**, pas sur le PC client.

---

## 🔧 Configuration Avancée

### Changer le port par défaut

Si le port 8088 est occupé, vous pouvez en utiliser un autre :

```powershell
# Dans app.py, modifiez la constante _DEFAULT_PORT
_DEFAULT_PORT = 9090
```

Ou lancez avec un port spécifique (si supporté par la CLI) :

```powershell
# À vérifier selon l'implémentation
ProFiles --server-only --port 9090
```

### IP statique pour le PC Hôte

Pour éviter que l'IP change à chaque redémarrage :

1. **Via le routeur** : Configurez une réservation DHCP pour le PC hôte
2. **Via Windows** : Configurez une IP statique manuelle

**Exemple de configuration statique** :

```
IP Address: 192.168.1.100
Subnet Mask: 255.255.255.0
Gateway: 192.168.1.1
DNS: 8.8.8.8
```

### Arrêter le serveur

Appuyez sur **Ctrl+C** dans le terminal où le serveur tourne.

---

## 🛡️ Sécurité

### Bonnes Pratiques

✅ **Faire** :
- Utiliser sur un réseau de confiance (bureau, domicile)
- Configurer le firewall Windows
- Limiter l'accès aux utilisateurs autorisés
- Surveiller les logs du serveur

❌ **Éviter** :
- **NE PAS** configurer de port forwarding sur le routeur
- **NE PAS** exposer sur Internet (WiFi public, réseau invité)
- **NE PAS** partager l'URL en dehors du réseau local
- **NE PAS** utiliser pour des fichiers sensibles sans authentification

### Niveau de Sécurité Actuel

⚠️ **Attention** : Cette configuration n'a **pas d'authentification**. Elle est conçue pour des réseaux locaux de confiance.

**Pour une sécurité renforcée** :
- Utilisez un VPN pour accéder au réseau
- Configurez un proxy inverse avec authentification (Nginx, Apache)
- Envisagez l'option B (authentification) pour une future évolution

---

## 🐛 Dépannage

### Problème: "Unable to connect" sur le PC client

**Cause** : Firewall bloquant le port 8088

**Solution** :
```powershell
# Vérifier la règle firewall sur le PC hôte
Get-NetFirewallRule -DisplayName "ProFiles Server"

# Si absente, recréer la règle
New-NetFirewallRule -DisplayName "ProFiles Server" -Direction Inbound -Protocol TCP -LocalPort 8088 -Action Allow
```

### Problème: "Connection refused"

**Cause** : Serveur non démarré ou port occupé

**Solution** :
```powershell
# Vérifier si le serveur tourne
netstat -ano | findstr :8088

# Si le port est occupé, changez de port ou arrêtez l'autre processus
taskkill /PID <PID> /F
```

### Problème: L'IP change à chaque redémarrage

**Cause** : DHCP attribue une IP différente

**Solution** :
- Configurez une réservation DHCP sur le routeur
- Ou configurez une IP statique sur le PC hôte

### Problème: "Network unreachable"

**Cause** : PC clients sur un sous-réseau différent

**Solution** :
- Vérifiez que tous les PC sont sur le même sous-réseau (ex: 192.168.1.x)
- Vérifiez le masque de sous-réseau (généralement 255.255.255.0)

### Problème: Les fichiers ne se lancent pas

**Cause** : Chemin de fichier incorrect ou fichier inexistant

**Solution** :
- Vérifiez que les fichiers existent sur le PC hôte
- Vérifiez les permissions d'accès aux fichiers
- Consultez les logs du serveur pour les erreurs

---

## 📊 Performance

### Limitations Connues

| Métrique | Valeur Recommandée |
|----------|-------------------|
| Nombre de fichiers | < 10 000 |
| Profondeur de répertoire | < 10 niveaux |
| Latence réseau | < 50 ms |
| Bande passante | > 100 Mbps |

### Optimisations

- **Scan initial** : Peut prendre quelques secondes pour de grands répertoires
- **Filtres** : Utilisez les filtres d'extension pour réduire la liste
- **Répertoire actif** : Sélectionnez un répertoire spécifique plutôt que le root

---

## 📝 Exemple d'Utilisation

### Scénario: Bureau partagé

**Contexte** : 3 PC dans un bureau, fichiers centralisés sur le PC principal

**Configuration** :
- **PC Hôte** : 192.168.1.100 (fichiers partagés)
- **PC Client 1** : 192.168.1.101
- **PC Client 2** : 192.168.1.102

**Workflow** :
1. PC Hôte : `ProFiles --server-only`
2. PC Client 1 : Navigateur → `http://192.168.1.100:8088`
3. PC Client 2 : Navigateur → `http://192.168.1.100:8088`
4. Tous peuvent scanner et lancer les fichiers du PC Hôte

---

## 🔮 Évolutions Futures

### Authentification (Option B)

Ajouter un token d'accès ou authentification basique pour sécuriser l'accès.

### Découverte Auto (Option C)

Utiliser mDNS/Bonjour pour que les PC clients trouvent automatiquement le serveur.

### HTTPS (Option D)

Chiffrer les communications avec un certificat SSL.

---

## 📚 Ressources

- [Spec technique](../specs/2026-10-15-network-server-design.md)
- [README principal](../../README.md)
- [Guide d'installation](../installation-guide.fr.md)

---

**Dernière mise à jour** : 2026-10-15  
**Auteur** : Équipe ProFiles  
**Version** : 1.0
