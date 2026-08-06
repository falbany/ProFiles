# MILESTONES.md — Roadmap des Fonctionnalités Futures

## 📅 Vision à Long Terme

Ce document recense les idées d'améliorations pour le moteur de recherche et les fonctionnalités associées de ProFiles. Ces fonctionnalités ne sont pas prioritaires mais représentent la feuille de route future.

---

## 🎯 Fonctionnalités Planifiées

### Milestone 1 : Autocomplétion Intelligente ⭐

**Statut** : À implémenter après la recherche par colonne

**Description** :
Système d'autocomplétion en temps réel pour guider les utilisateurs dans l'utilisation de la syntaxe `column:value`.

**Fonctionnalités** :

1. **Suggestions de Colonnes**
   - Affichage des colonnes disponibles quand l'utilisateur tape un texte suivi de `:`
   - Exemple : `Dev` + `:` → suggestions : `Device`, `Developer`, `Development`

2. **Suggestions de Valeurs**
   - Autocomplétion des valeurs uniques pour une colonne
   - Exemple : `Device:` → suggestions : `ABC123`, `DEF456`, `XYZ789`

3. **Historique des Recherches**
   - Sauvegarde des dernières recherches effectuées
   - Suggestions basées sur l'historique personnel

**Architecture** :

```python
# core/search_suggestions.py
class SearchSuggestions:
    """Générateur de suggestions pour la recherche."""
    
    def __init__(self, column_names: tuple[str, ...]):
        self._column_names = column_names
        self._unique_values: dict[str, set[str]] = {}
        self._search_history: list[str] = []
    
    def analyze_files(self, files: list[ScannedFileDynamic]) -> None:
        """Analyser les fichiers pour extraire les valeurs uniques."""
        self._unique_values.clear()
        
        for file_entry in files:
            for col_name, value in file_entry.column_values.items():
                if col_name not in self._unique_values:
                    self._unique_values[col_name] = set()
                self._unique_values[col_name].add(value)
    
    def get_column_suggestions(self, prefix: str = "") -> list[str]:
        """Suggérer des noms de colonnes."""
        if not prefix:
            return list(self._column_names)[:10]
        
        return [
            col for col in self._column_names
            if col.lower().startswith(prefix.lower())
        ][:10]
    
    def get_value_suggestions(
        self,
        column: str,
        prefix: str = "",
    ) -> list[str]:
        """Suggérer des valeurs pour une colonne."""
        if column not in self._unique_values:
            return []
        
        values = self._unique_values[column]
        if prefix:
            values = {
                v for v in values
                if v.lower().startswith(prefix.lower())
            }
        
        return sorted(values)[:10]
    
    def add_to_history(self, query: str) -> None:
        """Ajouter une recherche à l'historique."""
        if query in self._search_history:
            self._search_history.remove(query)
        
        self._search_history.insert(0, query)
        
        # Limiter à 20 entrées
        if len(self._search_history) > 20:
            self._search_history = self._search_history[:20]
    
    def get_history_suggestions(self, prefix: str = "") -> list[str]:
        """Suggérer des recherches de l'historique."""
        if not prefix:
            return self._search_history[:10]
        
        return [
            q for q in self._search_history
            if q.lower().startswith(prefix.lower())
        ][:10]
```

**Intégration GUI** :

```python
# gui/search_autocomplete.py
class SearchAutocomplete(tk.Frame):
    """Widget d'autocomplétion pour la recherche."""
    
    def __init__(
        self,
        parent: tk.Widget,
        suggestions: SearchSuggestions,
    ):
        super().__init__(parent)
        self._suggestions = suggestions
        self._popup: tk.Listbox | None = None
        
        # Entry principal
        self._entry = ttk.Entry(self)
        self._entry.pack(fill='x')
        
        # Liaison des événements
        self._entry.bind('<KeyRelease>', self._on_key_release)
        self._entry.bind('<FocusOut>', self._hide_popup)
        self._entry.bind('<Down>', self._navigate_down)
        self._entry.bind('<Up>', self._navigate_up)
        self._entry.bind('<Return>', self._select_highlighted)
        
        # Navigation clavier
        self._highlighted_index = -1
    
    def _on_key_release(self, event: tk.Event) -> None:
        """Gérer la frappe pour afficher les suggestions."""
        query = self._entry.get()
        
        if len(query) < 1:
            self._hide_popup()
            return
        
        # Ignorer les touches de contrôle
        if event.keysym in ('Return', 'Down', 'Up', 'Escape'):
            return
        
        suggestions = self._generate_suggestions(query)
        
        if suggestions:
            self._show_popup(suggestions)
        else:
            self._hide_popup()
    
    def _generate_suggestions(self, query: str) -> list[str]:
        """Générer des suggestions basées sur la requête."""
        suggestions = []
        
        if ':' in query:
            # Mode valeur de colonne
            col, prefix = query.rsplit(':', 1)
            col = col.strip()
            prefix = prefix.strip()
            
            if col in self._suggestions._unique_values:
                suggestions = self._suggestions.get_value_suggestions(
                    col, prefix
                )
                suggestions = [f"{col}:{s}" for s in suggestions]
        else:
            # Mode nom de colonne ou historique
            suggestions = self._suggestions.get_column_suggestions(query)
            suggestions = [f"{s}:" for s in suggestions]
            
            # Ajouter l'historique
            history = self._suggestions.get_history_suggestions(query)
            suggestions.extend(history)
        
        return suggestions[:15]  # Limiter à 15 suggestions
    
    def _show_popup(self, suggestions: list[str]) -> None:
        """Afficher la popup de suggestions."""
        if not self._popup:
            self._popup = tk.Listbox(self, height=8, width=50)
            self._popup.place(relx=0, rely=1, anchor='sw')
            self._popup.bind('<Double-Button-1>', self._select_suggestion)
            self._popup.bind('<Button-1>', self._highlight_suggestion)
        
        self._popup.delete(0, tk.END)
        for suggestion in suggestions:
            self._popup.insert(tk.END, suggestion)
        
        self._highlighted_index = 0
        self._popup.selection_clear(0, tk.END)
        self._popup.selection_set(0)
        
        self._popup.lift()
    
    def _hide_popup(self) -> None:
        """Masquer la popup."""
        if self._popup:
            self._popup.place_forget()
            self._highlighted_index = -1
    
    def _select_suggestion(self, event: tk.Event) -> None:
        """Sélectionner une suggestion."""
        selection = self._popup.curselection()
        if selection:
            value = self._popup.get(selection[0])
            self._entry.delete(0, tk.END)
            self._entry.insert(0, value)
            self._hide_popup()
            self._suggestions.add_to_history(value)
    
    def _highlight_suggestion(self, event: tk.Event) -> None:
        """Surligner une suggestion au survol."""
        selection = self._popup.curselection()
        if selection:
            self._highlighted_index = selection[0]
            self._popup.selection_clear(0, tk.END)
            self._popup.selection_set(self._highlighted_index)
    
    def _navigate_down(self, event: tk.Event) -> str:
        """Naviguer vers le bas dans les suggestions."""
        if self._popup and self._highlighted_index < len(self._popup.get(0, tk.END)) - 1:
            self._highlighted_index += 1
            self._popup.selection_clear(0, tk.END)
            self._popup.selection_set(self._highlighted_index)
        return 'break'
    
    def _navigate_up(self, event: tk.Event) -> str:
        """Naviguer vers le haut dans les suggestions."""
        if self._popup and self._highlighted_index > 0:
            self._highlighted_index -= 1
            self._popup.selection_clear(0, tk.END)
            self._popup.selection_set(self._highlighted_index)
        return 'break'
    
    def _select_highlighted(self, event: tk.Event) -> str:
        """Sélectionner l'élément surligné."""
        if self._popup and self._highlighted_index >= 0:
            value = self._popup.get(self._highlighted_index)
            self._entry.delete(0, tk.END)
            self._entry.insert(0, value)
            self._hide_popup()
            self._suggestions.add_to_history(value)
        return 'break'
```

**Estimation** : 3-4 jours de développement

---

### Milestone 2 : Interface de Filtres Avancés

**Statut** : À implémenter après autocomplétion

**Description** :
Interface graphique permettant de créer des filtres complexes sans connaître la syntaxe.

**Composants** :

1. **Panneau de Filtres Collapsible**
   - Bouton "Filtres avancés" pour afficher/masquer
   - Un champ par colonne disponible
   - Sélecteur d'opérateur pour chaque colonne

2. **Sélecteurs d'Opérateurs**
   - Contient (par défaut)
   - Égale exactement
   - Commence par
   - Termine par
   - Ne contient pas
   - Est vide
   - N'est pas vide

3. **Boutons d'Action**
   - "Appliquer" pour exécuter la recherche
   - "Effacer" pour réinitialiser tous les filtres
   - "Sauvegarder" pour enregistrer le filtre actuel

**Architecture** :

```python
# gui/advanced_filters.py
class AdvancedFiltersPanel(tk.Frame):
    """Panneau de filtres avancés par colonne."""
    
    def __init__(
        self,
        parent: tk.Widget,
        column_names: tuple[str, ...],
        on_apply: callable,
    ):
        super().__init__(parent)
        self._column_names = column_names
        self._on_apply = on_apply
        self._filter_entries: dict[str, ttk.Entry] = {}
        self._operator_combos: dict[str, ttk.Combobox] = {}
        
        self._create_widgets()
    
    def _create_widgets(self) -> None:
        """Créer les widgets pour chaque colonne."""
        for i, col_name in enumerate(self._column_names):
            if col_name == "File":
                continue  # Skip la colonne File
            
            # Frame pour cette ligne de filtre
            frame = ttk.Frame(self)
            frame.grid(row=i, column=0, sticky='ew', padx=5, pady=2)
            
            # Label colonne
            label = ttk.Label(frame, text=f"{col_name}:", width=15, anchor='e')
            label.pack(side='left')
            
            # Sélecteur d'opérateur
            operator_combo = ttk.Combobox(
                frame,
                values=[
                    'contient',
                    'égale',
                    'commence par',
                    'termine par',
                    'ne contient pas',
                    'est vide',
                    'n\'est pas vide',
                ],
                width=15,
            )
            operator_combo.current(0)
            operator_combo.pack(side='left', padx=5)
            
            # Champ de valeur
            entry = ttk.Entry(frame, width=30)
            entry.pack(side='left', padx=5)
            
            self._filter_entries[col_name] = entry
            self._operator_combos[col_name] = operator_combo
        
        # Boutons d'action
        btn_frame = ttk.Frame(self)
        btn_frame.grid(row=len(self._column_names), column=0, pady=10)
        
        apply_btn = ttk.Button(
            btn_frame,
            text="Appliquer",
            command=self._apply_filters,
        )
        apply_btn.pack(side='left', padx=5)
        
        clear_btn = ttk.Button(
            btn_frame,
            text="Effacer",
            command=self._clear_filters,
        )
        clear_btn.pack(side='left', padx=5)
    
    def _apply_filters(self) -> None:
        """Appliquer les filtres configurés."""
        filters = self.get_filters()
        query = self._build_query(filters)
        self._on_apply(query)
    
    def _clear_filters(self) -> None:
        """Effacer tous les filtres."""
        for entry in self._filter_entries.values():
            entry.delete(0, tk.END)
        for combo in self._operator_combos.values():
            combo.current(0)
    
    def get_filters(self) -> dict[str, dict[str, str]]:
        """Récupérer tous les filtres actifs."""
        filters = {}
        
        for col_name, entry in self._filter_entries.items():
            value = entry.get().strip()
            if value:
                operator = self._operator_combos[col_name].get()
                filters[col_name] = {
                    'value': value,
                    'operator': operator,
                }
        
        return filters
    
    def _build_query(self, filters: dict[str, dict[str, str]]) -> str:
        """Construire une requête de recherche à partir des filtres."""
        parts = []
        
        for col_name, filter_data in filters.items():
            value = filter_data['value']
            operator = filter_data['operator']
            
            if operator == 'contient':
                parts.append(f"{col_name}:{value}")
            elif operator == 'égale':
                parts.append(f'{col_name}:"{value}"')
            elif operator == 'commence par':
                parts.append(f"{col_name}:{value}*")
            elif operator == 'termine par':
                parts.append(f"{col_name}:*{value}")
            elif operator == 'ne contient pas':
                parts.append(f"-{col_name}:{value}")
            elif operator == 'est vide':
                parts.append(f"-{col_name}:*")
            elif operator == "n'est pas vide":
                parts.append(f"{col_name}:*")
        
        return " ".join(parts)
```

**Estimation** : 2-3 jours de développement

---

### Milestone 3 : Index Inversé pour Grandes Données

**Statut** : À implémenter si > 50,000 fichiers

**Description** :
Optimisation des performances pour les grands jeux de données via un index inversé.

**Voir** : `docs/search-improvement-proposals.md` section "Index Inversé (Option Avancée)"

**Estimation** : 3-5 jours de développement

---

### Milestone 4 : Sauvegarde des Filtres Fréquents

**Statut** : Fonctionnalité utilisateur

**Description** :
Permettre aux utilisateurs de sauvegarder et réutiliser des filtres fréquents.

**Fonctionnalités** :

1. **Sauvegarde de Filtres**
   - Bouton "Sauvegarder ce filtre"
   - Nom personnalisé pour chaque filtre
   - Stockage dans la configuration `.profiles`

2. **Chargement Rapide**
   - Menu déroulant "Filtres sauvegardés"
   - Chargement en un clic
   - Modification des filtres existants

3. **Gestion des Filtres**
   - Renommer un filtre
   - Supprimer un filtre
   - Exporter/Importer des filtres

**Architecture** :

```python
# core/saved_filters.py
class SavedFilters:
    """Gestion des filtres sauvegardés."""
    
    def __init__(self, config_path: Path):
        self._config_path = config_path
        self._filters: dict[str, dict] = {}
        self._load_filters()
    
    def _load_filters(self) -> None:
        """Charger les filtres depuis la configuration."""
        if self._config_path.exists():
            parser = configparser.ConfigParser()
            parser.read(self._config_path)
            
            for section in parser.sections():
                if section.startswith("FILTER_"):
                    filter_name = section[7:]
                    self._filters[filter_name] = {
                        'query': parser.get(section, 'query'),
                        'description': parser.get(section, 'description', fallback=''),
                        'created': parser.get(section, 'created', fallback=''),
                    }
    
    def save_filter(
        self,
        name: str,
        query: str,
        description: str = "",
    ) -> None:
        """Sauvegarder un filtre."""
        import datetime
        
        self._filters[name] = {
            'query': query,
            'description': description,
            'created': datetime.datetime.now().isoformat(),
        }
        
        self._write_filters()
    
    def delete_filter(self, name: str) -> None:
        """Supprimer un filtre."""
        if name in self._filters:
            del self._filters[name]
            self._write_filters()
    
    def get_filters(self) -> dict[str, dict]:
        """Obtenir tous les filtres sauvegardés."""
        return self._filters.copy()
    
    def _write_filters(self) -> None:
        """Écrire les filtres dans la configuration."""
        parser = configparser.ConfigParser()
        
        # Lire la configuration existante
        if self._config_path.exists():
            parser.read(self._config_path)
        
        # Supprimer les sections FILTER_* existantes
        sections_to_remove = [
            s for s in parser.sections()
            if s.startswith("FILTER_")
        ]
        for section in sections_to_remove:
            parser.remove_section(section)
        
        # Ajouter les nouveaux filtres
        for name, data in self._filters.items():
            section_name = f"FILTER_{name}"
            parser.add_section(section_name)
            parser.set(section_name, 'query', data['query'])
            parser.set(section_name, 'description', data.get('description', ''))
            parser.set(section_name, 'created', data.get('created', ''))
        
        # Écrire
        with open(self._config_path, 'w') as f:
            parser.write(f)
```

**Estimation** : 2 jours de développement

---

### Milestone 5 : Recherche dans le Contenu des Fichiers

**Statut** : Fonctionnalité avancée (optionnelle)

**Description** :
Permettre la recherche de texte dans le contenu des fichiers (pas seulement les noms).

**Attention** : Cette fonctionnalité peut être coûteuse en performance et stockage.

**Architecture** :

```python
# core/content_search.py
class ContentSearch:
    """Recherche de texte dans le contenu des fichiers."""
    
    def __init__(self, cache_dir: Path):
        self._cache_dir = cache_dir
        self._content_index: dict[str, set[int]] = {}
    
    def index_file(self, file_path: Path, file_index: int) -> None:
        """Indexer le contenu d'un fichier."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
            
            # Tokeniser le contenu
            words = self._tokenize(content)
            
            for word in words:
                if word not in self._content_index:
                    self._content_index[word] = set()
                self._content_index[word].add(file_index)
        
        except Exception as e:
            # Fichier non lisible, ignorer
            pass
    
    def search(self, query: str) -> set[int]:
        """Rechercher dans le contenu indexé."""
        words = self._tokenize(query)
        
        if not words:
            return set()
        
        # Intersection de tous les mots (AND)
        results = None
        for word in words:
            if word in self._content_index:
                word_results = self._content_index[word]
                if results is None:
                    results = word_results
                else:
                    results &= word_results
            else:
                return set()
        
        return results or set()
    
    def _tokenize(self, text: str) -> list[str]:
        """Tokeniser le texte en mots."""
        import re
        # Convertir en minuscules et extraire les mots
        words = re.findall(r'\w+', text.lower())
        # Filtrer les mots trop courts
        return [w for w in words if len(w) >= 3]
```

**Estimation** : 4-5 jours de développement

---

## 📊 Estimation Totale

| Milestone | Estimation | Priorité |
|-----------|------------|----------|
| 1. Autocomplétion | 3-4 jours | Moyenne |
| 2. Filtres graphiques | 2-3 jours | Faible |
| 3. Index inversé | 3-5 jours | Conditionnelle |
| 4. Filtres sauvegardés | 2 jours | Faible |
| 5. Recherche contenu | 4-5 jours | Très faible |

**Total** : 14-19 jours (hors recherche contenu : 10-12 jours)

---

## 🔄 Ordre d'Implémentation Recommandé

1. **Recherche par colonne** (document principal) — PRIORITÉ HAUTE
2. **Autocomplétion** — Améliore l'UX immédiatement après
3. **Filtres sauvegardés** — Fonctionnalité utilisateur utile
4. **Index inversé** — Seulement si besoin de performance
5. **Filtres graphiques** — Optionnel si autocomplétion suffisante
6. **Recherche contenu** — Fonctionnalité avancée optionnelle

---

## 📝 Notes de Développement

### Dépendances

- Milestone 1 dépend de la recherche par colonne
- Milestone 3 dépend de l'analyse des performances réelles
- Milestone 5 est indépendant mais coûteux

### Points d'Attention

- L'autocomplétion nécessite l'analyse des valeurs uniques (coût mémoire)
- L'index inversé doit être reconstruit à chaque nouveau scan
- La recherche de contenu peut être très lente sur de gros fichiers

### Métriques de Succès

- Temps de recherche < 100ms pour 10k fichiers
- Utilisation mémoire < 100MB pour 50k fichiers
- 90% des utilisateurs utilisent la recherche par colonne

---

## 📅 Historique des Versions

### v2.0 (Planifié)
- Recherche par colonne (Milestone principal)
- Autocomplétion basique

### v2.1 (Planifié)
- Filtres sauvegardés
- Améliorations UX autocomplétion

### v2.2 (Optionnel)
- Index inversé
- Filtres graphiques avancés

### v3.0 (Futur)
- Recherche dans le contenu
- Fonctionnalités collaboratives
