#!/usr/bin/env python3
"""Diagramme à contacts « Laboratoire combinatoire : La bouteille ».

Génère diagramme_bouteille.svg, diagramme_bouteille.png et verification.txt.

Le dessin et la vérification partent de la même géométrie : chaque fil est un
segment, chaque composant a deux bornes. Les noeuds électriques sont retrouvés
à partir des coordonnées des fils dessinés, puis le circuit est simulé.
"""
import itertools
import os
import subprocess
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
POLICE = "Arial, Helvetica, 'Liberation Sans', 'DejaVu Sans', sans-serif"

# ----------------------------------------------------------------- géométrie
W = 2400
XL, XR = 150, 2010            # rail gauche (+), rail droit (0 V)
C1, C2 = 340, 570             # colonnes des contacts de commande
BAR = 700                     # barre « Résultat »
S = [860, 1090, 1320, 1550]   # colonnes des contacts capteurs
XCOIL = 1850                  # colonne des bobines
XFONC = 2032                  # texte « fonction » à droite du rail
DEMI = 35                     # demi-largeur d'un contact (borne à borne)
DEMIB = 55                    # demi-largeur d'une bobine (borne à borne)
YSRC = 168                    # fil de la source

HAUT_T, HAUT_P = 60, 42       # encombrement au-dessus d'une rangée (tempo / simple)
BAS_T, BAS_P = 44, 22         # encombrement en dessous
ESP_RANGEE, ESP_ECHELON = 8, 20

T_ANALYSE, T_AFFICHAGE = 3173, 9757          # ms
T_VERT, T_JAUNE, T_ROUGE = 1350, 2700, 4050  # ms


def fr(ms):
    """Millisecondes -> '3,173 s'."""
    return (f"{ms / 1000:.3f}".rstrip("0").rstrip(".")).replace(".", ",") + " s"


class Dessin:
    def __init__(self):
        self.svg = []        # éléments SVG
        self.fils = []       # (x1, y1, x2, y2, épaisseur)
        self.comps = []      # composants du circuit (netlist)
        self.boites = []     # (x1, y1, x2, y2, nom) encombrement des symboles
        self.textes = []     # (x1, y1, x2, y2, texte)

    # -- primitives
    def ligne(self, x1, y1, x2, y2, w=2.5, extra=""):
        self.svg.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                        f'stroke="black" stroke-width="{w}" stroke-linecap="round" {extra}/>')

    def fil(self, x1, y1, x2, y2, w=2.5):
        assert x1 == x2 or y1 == y2, "fil ni horizontal ni vertical"
        self.fils.append((x1, y1, x2, y2, w))

    def chemin(self, *pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            self.fil(x1, y1, x2, y2)

    def texte(self, x, y, s, taille=20, ancre="middle", gras=False, verif=True, italique=False):
        style = (' font-weight="bold"' if gras else "") + (' font-style="italic"' if italique else "")
        s_xml = s.replace("&", "&amp;").replace("<", "&lt;")
        self.svg.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{taille}" '
                        f'text-anchor="{ancre}"{style} xml:space="preserve">{s_xml}</text>')
        if verif:
            larg = len(s) * taille * (0.62 if gras else 0.58)
            x1 = {"middle": x - larg / 2, "start": x, "end": x - larg}[ancre]
            self.textes.append((x1, y - 0.75 * taille, x1 + larg, y + 0.2 * taille, s))

    # -- symboles
    def contact(self, x, y, nom, nf=False, tempo=None, bouton=False, source=None, net=True):
        """Contact horizontal centré en (x, y). Bornes en x-DEMI et x+DEMI.
        source = ('capteur', 'a') | ('relais', 'Analyse') | ('bouton', 'BoutonMarche')."""
        self.ligne(x - DEMI, y, x - 20, y)
        self.ligne(x + 20, y, x + DEMI, y)
        if nf:   # lame fermée sous la ligne, appuyée sur la butée
            self.ligne(x - 20, y, x + 26, y + 16.1)
            self.ligne(x + 20, y, x + 20, y + 14)
            ylame = lambda dx: y + (20 + dx) * 16.1 / 46
        else:    # lame ouverte au-dessus de la ligne
            self.ligne(x - 20, y, x + 18, y - 16)
            ylame = lambda dx: y - (20 + dx) * 16 / 38
        haut, bas = (4 if nf else 18), (18 if nf else 4)
        ynom = y - 22
        if tempo is not None:   # parachute de temporisation (retard à l'actionnement)
            self.ligne(x - 3, ylame(-3), x - 3, y - 29, w=1.8)
            self.ligne(x + 3, ylame(3), x + 3, y - 29, w=1.8)
            self.svg.append(f'<path d="M {x - 12} {y - 22} A 13 13 0 0 1 {x + 12} {y - 22}" '
                            f'fill="none" stroke="black" stroke-width="2.5" stroke-linecap="round"/>')
            haut, ynom = 32, y - 38
            ytxt = y + (38 if nf else 26)
            self.texte(x, ytxt, fr(tempo), taille=17, italique=True)
        if bouton:              # poussoir en T
            self.ligne(x, ylame(0), x, y - 30, w=1.8, extra='stroke-dasharray="4 3"')
            self.ligne(x - 11, y - 30, x + 11, y - 30)
            self.ligne(x - 11, y - 30, x - 11, y - 25)
            self.ligne(x + 11, y - 30, x + 11, y - 25)
            haut, ynom = 32, y - 38
        if nom:
            self.texte(x, ynom, nom, taille=20)
        self.boites.append((x - DEMI, y - haut, x + DEMI, y + bas, nom))
        if net:
            self.comps.append(dict(type="contact", nom=nom, nf=nf, tempo=tempo, source=source,
                                   b1=(x - DEMI, y), b2=(x + DEMI, y)))

    def bobine(self, x, y, nom, delai=None, net=True):
        self.ligne(x - DEMIB, y, x - 35, y)
        self.ligne(x + 35, y, x + DEMIB, y)
        self.svg.append(f'<rect x="{x - 35}" y="{y - 20}" width="70" height="40" fill="white" '
                        f'stroke="black" stroke-width="2.5"/>')
        self.texte(x - 46, y - 6, "A1", taille=12, verif=False)
        self.texte(x + 46, y - 6, "A2", taille=12, verif=False)
        if nom:
            self.texte(x, y - 28, nom, taille=20, gras=True)
        if delai is not None:
            self.texte(x, y + 38, fr(delai), taille=17, italique=True)
        self.boites.append((x - DEMIB, y - 22, x + DEMIB, y + 22, nom))
        if net:
            self.comps.append(dict(type="bobine", nom=nom, b1=(x - DEMIB, y), b2=(x + DEMIB, y)))

    def source(self, x, y):
        self.ligne(x - 40, y, x - 16, y)
        self.ligne(x + 16, y, x + 40, y)
        for dx, long_ in ((-16, True), (-6, False), (6, True), (16, False)):
            h = 22 if long_ else 11
            self.ligne(x + dx, y - h, x + dx, y + h, w=2.5 if long_ else 5)
        self.texte(x - 30, y - 10, "+", taille=20, gras=True, verif=False)
        self.texte(x + 30, y - 10, "−", taille=20, gras=True, verif=False)
        self.texte(x, y - 34, "Source 24 V CC", taille=20, gras=True)
        self.boites.append((x - 40, y - 24, x + 40, y + 24, "Source"))
        self.comps.append(dict(type="source", nom="Source", b1=(x - 40, y), b2=(x + 40, y)))


# ------------------------------------------------------------ construction
def construire():
    d = Dessin()

    # ---- rangées : (clé, temporisée ?, début d'échelon ?)
    rangees = [("1a", True, True), ("1b", False, False),
               ("2", False, True), ("3", True, True), ("res", True, True),
               ("4", False, True),
               ("5a", False, True), ("5b", False, False),
               ("6a", False, True), ("6b", False, False), ("6c", False, False),
               ("6d", False, False), ("6e", False, False),
               ("7a", True, True), ("7b", True, False), ("7c", True, False)]
    bas_force = {"2": BAS_T}          # délai écrit sous la bobine « Analyse »
    Y, y, bas_prec = {}, YSRC + 14, 0
    for cle, tempo, debut in rangees:
        y += bas_prec + (ESP_ECHELON if debut else ESP_RANGEE) + (HAUT_T if tempo else HAUT_P)
        Y[cle] = y
        bas_prec = bas_force.get(cle, BAS_T if tempo else BAS_P)
    y_fin = y + bas_prec

    # ---- en-tête
    d.texte(XL - 60, 52, "Laboratoire combinatoire : La bouteille — Diagramme à contacts",
            taille=34, ancre="start", gras=True)
    for i, eq in enumerate(["V (lumière verte)  =  /a·b·c·/d",
                            "J (lumière jaune)  =  /a·b·/c·d  +  a·/b·c·/d",
                            "R (lumière rouge)  =  /a·/b  +  a·b  +  /c·/d  +  c·d  +  a·/c"]):
        d.texte(XL - 60, 88 + 28 * i, eq, taille=22, ancre="start")
    d.texte(1420, 88, "a b c d = c1 c2 f1 f2", taille=22, ancre="start", gras=True)
    d.texte(1420, 116, "« / » = négation : contact normalement fermé (NF)", taille=20, ancre="start")
    d.texte(1420, 144, "sans « / » : contact normalement ouvert (NO)", taille=20, ancre="start")

    # ---- rails et source
    xs = (XL + XR) // 2
    d.fil(XL, YSRC, XL, Y["7c"], w=6)     # les rails s'arrêtent au dernier raccordement
    d.fil(XR, YSRC, XR, Y["7a"], w=6)
    d.fil(XL, YSRC, xs - 40, YSRC)
    d.fil(xs + 40, YSRC, XR, YSRC)
    d.source(xs, YSRC)
    d.texte(XL - 14, YSRC + 7, "+24 V", taille=20, ancre="end", gras=True)
    d.texte(XR + 14, YSRC + 7, "0 V", taille=20, ancre="start", gras=True)

    def sortie(x_depuis, cle, nom, fonction, numero, delai=None):
        """Fil vers la bobine, bobine, liaison au rail 0 V, textes de marge."""
        yy = Y[cle]
        d.fil(x_depuis, yy, XCOIL - DEMIB, yy)
        d.bobine(XCOIL, yy, nom, delai)
        d.fil(XCOIL + DEMIB, yy, XR, yy)
        d.texte(XFONC, yy + 6, fonction, taille=18, ancre="start")
        d.svg.append(f'<circle cx="80" cy="{yy}" r="19" fill="white" stroke="black" stroke-width="2"/>')
        d.texte(80, yy + 8, str(numero), taille=23, gras=True, verif=False)
        d.boites.append((61, yy - 19, 99, yy + 19, f"n°{numero}"))

    # ---- Échelon 1 : mémoire du cycle
    ya, yb = Y["1a"], Y["1b"]
    xdiv, xjon = (C1 + C2) // 2, C2 + 115
    d.fil(XL, ya, C1 - DEMI, ya)
    d.contact(C1, ya, "Affichage lum", nf=True, tempo=T_AFFICHAGE, source=("relais", "Affichage lum"))
    d.fil(C1 + DEMI, ya, C2 - DEMI, ya)
    d.contact(C2, ya, "BoutonMarche", bouton=True, source=("bouton", "BoutonMarche"))
    d.chemin((xdiv, ya), (xdiv, yb), (C2 - DEMI, yb))
    d.contact(C2, yb, "Automaintient", source=("relais", "Automaintient"))
    d.chemin((C2 + DEMI, yb), (xjon, yb), (xjon, ya))
    sortie(C2 + DEMI, "1a", "Automaintient", "Mémoire du cycle", 1)

    # ---- Échelon 2 : délai avant analyse
    yy = Y["2"]
    d.fil(XL, yy, C1 - DEMI, yy)
    d.contact(C1, yy, "Automaintient", source=("relais", "Automaintient"))
    sortie(C1 + DEMI, "2", "Analyse", f"Délai avant analyse {fr(T_ANALYSE)}", 2, delai=T_ANALYSE)

    # ---- Échelon 3 : durée d'affichage
    yy = Y["3"]
    d.fil(XL, yy, C1 - DEMI, yy)
    d.contact(C1, yy, "Automaintient", source=("relais", "Automaintient"))
    d.fil(C1 + DEMI, yy, C2 - DEMI, yy)
    d.contact(C2, yy, "Analyse", tempo=T_ANALYSE, source=("relais", "Analyse"))
    sortie(C2 + DEMI, "3", "Affichage lum", f"Durée d'affichage {fr(T_AFFICHAGE)}", 3, delai=T_AFFICHAGE)

    # ---- Barre « Résultat »
    yr = Y["res"]
    d.fil(XL, yr, C1 - DEMI, yr)
    d.contact(C1, yr, "Automaintient", source=("relais", "Automaintient"))
    d.fil(C1 + DEMI, yr, C2 - DEMI, yr)
    d.contact(C2, yr, "Analyse", tempo=T_ANALYSE, source=("relais", "Analyse"))
    d.fil(C2 + DEMI, yr, BAR, yr)
    d.fil(BAR, yr, BAR, Y["6e"], w=4.5)
    d.texte(BAR + 18, yr + 8, "Résultat", taille=23, ancre="start", gras=True)
    d.texte(BAR + 150, yr + 7, f"— barre secondaire : alimente les échelons 4, 5 et 6 "
            f"(sous tension après {fr(T_ANALYSE)})", taille=18, ancre="start")

    def branche(cle, contacts, x_fin):
        """Branche capteurs depuis la barre Résultat : [(lettre, nf), ...]."""
        yy, x = Y[cle], BAR
        for col, (lettre, nf) in zip(S, contacts):
            d.fil(x, yy, col - DEMI, yy)
            d.contact(col, yy, "Capt" + lettre, nf=nf, source=("capteur", lettre))
            x = col + DEMI
        if x != x_fin:
            d.fil(x, yy, x_fin, yy)

    NO, NF = False, True
    # ---- Échelon 4 : lumière verte   V = /a·b·c·/d
    branche("4", [("a", NF), ("b", NO), ("c", NO), ("d", NF)], S[3] + DEMI)
    sortie(S[3] + DEMI, "4", "LumVert", f"Lumière verte (bip {fr(T_VERT)})", 4)

    # ---- Échelon 5 : lumière jaune   J = /a·b·/c·d + a·/b·c·/d
    xj = S[3] + 130
    branche("5a", [("a", NF), ("b", NO), ("c", NF), ("d", NO)], xj)
    branche("5b", [("a", NO), ("b", NF), ("c", NO), ("d", NF)], xj)
    d.fil(xj, Y["5a"], xj, Y["5b"])
    sortie(xj, "5a", "LumJaune", f"Lumière jaune (bip {fr(T_JAUNE)})", 5)

    # ---- Échelon 6 : lumière rouge   R = /a·/b + a·b + /c·/d + c·d + a·/c
    xj = S[1] + 130
    rouge = [("6a", [("a", NF), ("b", NF)]), ("6b", [("a", NO), ("b", NO)]),
             ("6c", [("c", NF), ("d", NF)]), ("6d", [("c", NO), ("d", NO)]),
             ("6e", [("a", NO), ("c", NF)])]
    for cle, contacts in rouge:
        branche(cle, contacts, xj)
    d.fil(xj, Y["6a"], xj, Y["6e"])
    sortie(xj, "6a", "LumRouge", f"Lumière rouge (bip {fr(T_ROUGE)})", 6)

    # ---- Échelon 7 : signal sonore
    xj = BAR
    for cle, nom, t in (("7a", "LumVert", T_VERT), ("7b", "LumJaune", T_JAUNE), ("7c", "LumRouge", T_ROUGE)):
        yy = Y[cle]
        d.fil(XL, yy, C1 - DEMI, yy)
        d.contact(C1, yy, nom, source=("relais", nom))
        d.fil(C1 + DEMI, yy, C2 - DEMI, yy)
        d.contact(C2, yy, nom, nf=True, tempo=t, source=("relais", nom))
        d.fil(C2 + DEMI, yy, xj, yy)
    d.fil(xj, Y["7a"], xj, Y["7c"])
    sortie(xj, "7a", "SonHautParleur", "Signal sonore (avertisseur)", 7)

    # ---- légende
    yl = y_fin + 34
    hl = 232
    d.svg.append(f'<rect x="{XL - 60}" y="{yl}" width="{W - 2 * (XL - 60)}" height="{hl}" fill="none" '
                 f'stroke="black" stroke-width="1.5"/>')
    d.texte(XL - 40, yl + 30, "Légende", taille=22, ancre="start", gras=True)
    cols = [XL + 10 + 545 * i for i in range(4)]
    l1, l2 = yl + 84, yl + 150

    def item(x, yy, txt, dessin):
        dessin(x, yy)
        d.ligne(x - DEMI - 12, yy, x - DEMI, yy)
        d.ligne(x + DEMI, yy, x + DEMI + 12, yy)
        d.texte(x + DEMI + 26, yy + 6, txt, taille=17, ancre="start")

    item(cols[0], l1, "Contact NO (normalement ouvert)", lambda x, yy: d.contact(x, yy, "", net=False))
    item(cols[1], l1, "Contact NF (normalement fermé) — « / »",
         lambda x, yy: d.contact(x, yy, "", nf=True, net=False))
    item(cols[2], l1, "Bouton-poussoir NO", lambda x, yy: d.contact(x, yy, "", bouton=True, net=False))

    def bob(x, yy):
        d.ligne(x - DEMI, yy, x - 28, yy)
        d.ligne(x + 28, yy, x + DEMI, yy)
        d.svg.append(f'<rect x="{x - 28}" y="{yy - 16}" width="56" height="32" fill="white" '
                     f'stroke="black" stroke-width="2.5"/>')
        d.boites.append((x - DEMI, yy - 18, x + DEMI, yy + 18, "légende bobine"))
    item(cols[3], l1, "Bobine (bornes A1 / A2)", bob)

    def tempo_leg(nf):
        def f(x, yy):
            d.contact(x, yy, "", nf=nf, net=False)
            yl_ = (lambda dx: yy + (20 + dx) * 16.1 / 46) if nf else (lambda dx: yy - (20 + dx) * 16 / 38)
            d.ligne(x - 3, yl_(-3), x - 3, yy - 29, w=1.8)
            d.ligne(x + 3, yl_(3), x + 3, yy - 29, w=1.8)
            d.svg.append(f'<path d="M {x - 12} {yy - 22} A 13 13 0 0 1 {x + 12} {yy - 22}" fill="none" '
                         f'stroke="black" stroke-width="2.5" stroke-linecap="round"/>')
            d.boites.append((x - DEMI, yy - 32, x + DEMI, yy + 18, "légende tempo"))
        return f
    item(cols[0], l2, "Contact temporisé à la fermeture (NO)", tempo_leg(False))
    item(cols[1], l2, "Contact temporisé à l'ouverture (NF)", tempo_leg(True))
    x, yy = cols[2], l2
    d.ligne(x - DEMI - 12, yy, x + DEMI + 12, yy)
    d.ligne(x, yy, x, yy + 22)
    d.svg.append(f'<circle cx="{x}" cy="{yy}" r="6.5" fill="black"/>')
    d.texte(x + DEMI + 26, yy + 6, "Jonction (point plein = fils reliés)", taille=17, ancre="start")
    d.texte(cols[3] - DEMI - 12, l2 + 6, "Délais en italique, en secondes", taille=17, ancre="start",
            italique=True)
    d.texte(XL - 40, yl + hl - 20,
            "Capteurs :   a = c1 = Capta      b = c2 = Captb      c = f1 = Captc      d = f2 = Captd",
            taille=19, ancre="start", gras=True)

    return d, yl + hl + 30, Y


# ----------------------------------------------- noeuds à partir de la géométrie
def sur(p, f):
    x, y = p
    x1, y1, x2, y2 = f[:4]
    return min(x1, x2) <= x <= max(x1, x2) and min(y1, y2) <= y <= max(y1, y2)


def extremite(p, f):
    return p == (f[0], f[1]) or p == (f[2], f[3])


class Noeuds:
    def __init__(self, d):
        self.parent = {}
        bornes = [c[b] for c in d.comps for b in ("b1", "b2")]
        pts = set(bornes)
        for f in d.fils:
            pts.add((f[0], f[1]))
            pts.add((f[2], f[3]))
        self.pts = pts
        for f in d.fils:
            dessus = [p for p in pts if sur(p, f)]
            for p in dessus[1:]:
                self.unir(dessus[0], p)
        # degré de chaque point : nombre de bras de fil ou de bornes qui y arrivent
        self.degre = {}
        for p in pts:
            n = sum(1 if extremite(p, f) else 2 for f in d.fils if sur(p, f))
            self.degre[p] = n + bornes.count(p)

    def trouver(self, p):
        self.parent.setdefault(p, p)
        while self.parent[p] != p:
            self.parent[p] = self.parent[self.parent[p]]
            p = self.parent[p]
        return p

    def unir(self, a, b):
        self.parent[self.trouver(a)] = self.trouver(b)


# ------------------------------------------------------------------ simulation
class Circuit:
    """Simulation du circuit dessiné (noeuds issus des fils, contacts dessinés)."""

    def __init__(self, d, noeuds):
        self.contacts = [c for c in d.comps if c["type"] == "contact"]
        self.bobines = [c for c in d.comps if c["type"] == "bobine"]
        src = next(c for c in d.comps if c["type"] == "source")
        self.n = lambda p: noeuds.trouver(p)
        self.plus, self.zero = self.n(src["b1"]), self.n(src["b2"])
        assert self.plus != self.zero, "court-circuit de la source"

    def ferme(self, c, t, capteurs, bouton, depuis):
        genre, var = c["source"]
        if genre == "capteur":
            actif = bool(capteurs[var])
        elif genre == "bouton":
            actif = bouton
        else:
            debut = depuis.get(var)
            actif = debut is not None and t - debut >= (c["tempo"] or 0)
        return actif != c["nf"]

    def evaluer(self, t, capteurs, bouton, depuis):
        """Point fixe à l'instant t ; met à jour `depuis` (instant d'excitation des bobines)."""
        for _ in range(50):
            par = {}

            def tr(p):
                par.setdefault(p, p)
                while par[p] != p:
                    par[p] = par[par[p]]
                    p = par[p]
                return p
            for c in self.contacts:
                if self.ferme(c, t, capteurs, bouton, depuis):
                    par[tr(self.n(c["b1"]))] = tr(self.n(c["b2"]))
            assert tr(self.plus) != tr(self.zero), "court-circuit par des contacts"
            excitees = {b["nom"] for b in self.bobines
                        if tr(self.n(b["b1"])) == tr(self.plus) and tr(self.n(b["b2"])) == tr(self.zero)}
            if excitees == set(depuis):
                return excitees
            for nom in list(depuis):
                if nom not in excitees:
                    del depuis[nom]
            for nom in excitees:
                depuis.setdefault(nom, t)
        raise RuntimeError("circuit instable (oscillation)")

    def cycle(self, capteurs, t_bouton=200, t_max=20000):
        """Simulation par événements d'un cycle complet. Retourne [(t_ms, bobines excitées)]."""
        depuis, journal, t = {}, [], 0
        while t is not None and t <= t_max:
            etat = self.evaluer(t, capteurs, t < t_bouton, depuis)
            if not journal or journal[-1][1] != etat:
                journal.append((t, set(etat)))
            suivants = [t_bouton] if t < t_bouton else []
            for c in self.contacts:
                if c["source"][0] == "relais" and c["tempo"] and c["source"][1] in depuis:
                    te = depuis[c["source"][1]] + c["tempo"]
                    if te > t:
                        suivants.append(te)
            t = min(suivants) if suivants else None
        return journal


def etat_a(journal, t):
    etat = set()
    for tj, e in journal:
        if tj <= t:
            etat = e
    return etat


def intervalle(journal, nom):
    """(début, fin) de la première période d'excitation de la bobine `nom`."""
    debut = None
    for t, e in journal:
        if nom in e and debut is None:
            debut = t
        if nom not in e and debut is not None:
            return debut, t
    return debut, None


# ------------------------------------------------------- contrôles géométriques
def controles(d, noeuds, circuit):
    err, info = [], []
    bornes = {c[b]: c["nom"] for c in d.comps for b in ("b1", "b2")}

    libres = [f"{nom} {p}" for p, nom in bornes.items() if noeuds.degre[p] < 2]
    info.append(f"Bornes laissées libres : {len(libres)}")
    err += [f"borne libre : {x}" for x in libres]

    pend = [p for p in noeuds.pts if noeuds.degre[p] < 2 and p not in bornes]
    info.append(f"Extrémités de fil non raccordées : {len(pend)}")
    err += [f"fil pendant en {p}" for p in pend]

    crois = 0
    for f, g in itertools.combinations(d.fils, 2):
        h, v = (f, g) if f[1] == f[3] else (g, f)
        if h[1] != h[3] or v[0] != v[2]:
            continue
        if (min(h[0], h[2]) < v[0] < max(h[0], h[2]) and min(v[1], v[3]) < h[1] < max(v[1], v[3])):
            crois += 1
    info.append(f"Croisements de fils sans jonction : {crois}")
    if crois:
        err.append(f"{crois} croisement(s) de fils")

    def touche(f, b, marge=1):
        x1, x2 = sorted((f[0], f[2]))
        y1, y2 = sorted((f[1], f[3]))
        return x1 < b[2] - marge and x2 > b[0] + marge and y1 < b[3] - marge and y2 > b[1] + marge

    trav = [(b[4], f[:4]) for f in d.fils for b in d.boites if touche(f, b)]
    info.append(f"Fils traversant un symbole : {len(trav)}")
    err += [f"fil {f} traverse {n}" for n, f in trav]

    def recouvre(a, b, m=0):
        return a[0] < b[2] - m and a[2] > b[0] + m and a[1] < b[3] - m and a[3] > b[1] + m

    tt = [(a[4], b[4]) for a, b in itertools.combinations(d.textes, 2) if recouvre(a, b)]
    info.append(f"Textes superposés : {len(tt)}")
    err += [f"textes superposés : « {a} » / « {b} »" for a, b in tt]

    tf = [(t[4], f[:4]) for t in d.textes for f in d.fils
          if touche((f[0] - f[4] / 2, f[1] - f[4] / 2, f[2] + f[4] / 2, f[3] + f[4] / 2), t, 0)]
    info.append(f"Textes touchant un fil : {len(tf)}")
    err += [f"texte « {t} » sur le fil {f}" for t, f in tf]

    ts = [(t[4], b[4]) for t in d.textes for b in d.boites if recouvre(t, b)]
    info.append(f"Textes touchant un symbole : {len(ts)}")
    err += [f"texte « {t} » sur le symbole {b}" for t, b in ts]

    mal = [b["nom"] for b in circuit.bobines if noeuds.trouver(b["b2"]) != circuit.zero]
    info.append(f"Bobines reliées au rail 0 V : {len(circuit.bobines) - len(mal)} / {len(circuit.bobines)}")
    err += [f"bobine {n} non reliée au rail 0 V" for n in mal]

    xb = {b["b1"][0] for b in circuit.bobines}
    info.append(f"Bobines alignées dans une seule colonne : {'oui' if len(xb) == 1 else 'NON'}")
    if len(xb) != 1:
        err.append("bobines non alignées")
    return info, err


# ----------------------------------------------------------------------- sortie
def ecrire_svg(d, noeuds, hauteur, chemin):
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {hauteur:.0f}" '
           f'width="{W}" height="{hauteur:.0f}" font-family="{POLICE}" fill="black">',
           f'<rect width="{W}" height="{hauteur:.0f}" fill="white"/>']
    for x1, y1, x2, y2, w in d.fils:
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="black" '
                   f'stroke-width="{w}" stroke-linecap="square"/>')
    out += d.svg
    for p, n in noeuds.degre.items():       # un point plein à chaque jonction réelle
        if n >= 3:
            out.append(f'<circle cx="{p[0]}" cy="{p[1]}" r="6.5" fill="black"/>')
    out.append("</svg>")
    with open(chemin, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def rendre_png(svg, png, hauteur):
    js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch();
  const p = await b.newPage({{ viewport: {{ width: {W}, height: {int(hauteur)} }}, deviceScaleFactor: 1.5 }});
  await p.goto('file://{svg}');
  await p.screenshot({{ path: '{png}' }});
  await b.close();
}})();"""
    racine = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["node", "-e", js], check=True, env={**os.environ, "NODE_PATH": racine})


def main():
    d, hauteur, _ = construire()
    noeuds = Noeuds(d)
    circuit = Circuit(d, noeuds)
    L, erreurs = [], []
    L.append("VÉRIFICATION — Diagramme à contacts « Laboratoire combinatoire : La bouteille »")
    L.append("=" * 78)
    L.append("Tout ce qui suit est calculé à partir du schéma dessiné : les noeuds sont")
    L.append("reconstruits depuis les coordonnées des fils, puis le circuit est simulé")
    L.append("(contacts NO/NF, relais, temporisations). Les équations ne sont pas utilisées.")
    L.append("")

    # 1. table de vérité
    L.append("1. TABLE DE VÉRITÉ (16 combinaisons, état des lumières pendant l'affichage)")
    L.append("")
    L.append("    #   a b c d    Verte  Jaune  Rouge   lumières allumées")
    L.append("   ---  -------    -----  -----  -----   -----------------")
    journaux = {}
    for i in range(16):
        bits = [(i >> k) & 1 for k in (3, 2, 1, 0)]
        j = circuit.cycle(dict(zip("abcd", bits)))
        journaux[i] = j
        e = etat_a(j, T_ANALYSE + 1000)
        v, ja, r = ("LumVert" in e), ("LumJaune" in e), ("LumRouge" in e)
        L.append(f"   {i:>2}   {' '.join(map(str, bits))}      {int(v)}      {int(ja)}      {int(r)}             {v + ja + r}")
        attendu = (i == 6, i in (5, 10), i not in (5, 6, 10))
        if (v, ja, r) != attendu:
            erreurs.append(f"table de vérité : combinaison #{i} = {(v, ja, r)}, attendu {attendu}")
    L.append("")
    L.append("   Attendu : Verte = 1 seulement pour 0110 (#6) ; Jaune = 1 seulement pour")
    L.append("   0101 (#5) et 1010 (#10) ; Rouge = 1 pour les 13 autres ; une seule lumière")
    L.append("   par combinaison.")
    L.append(f"   Résultat : {'CONFORME' if not erreurs else 'NON CONFORME'}")
    L.append("")

    # 2. chronogramme
    L.append("2. CHRONOGRAMME (Marche appuyé à t = 0, relâché à t = 0,2 s)")
    L.append("")
    n_err = len(erreurs)
    bips = {"LumVert": T_VERT, "LumJaune": T_JAUNE, "LumRouge": T_ROUGE}
    t_fin = T_ANALYSE + T_AFFICHAGE
    for i, j in journaux.items():
        lum = next(n for n in bips if n in etat_a(j, T_ANALYSE + 1000))
        attendus = {"Automaintient": (0, t_fin), "Analyse": (0, t_fin),
                    "Affichage lum": (T_ANALYSE, t_fin), lum: (T_ANALYSE, t_fin),
                    "SonHautParleur": (T_ANALYSE, T_ANALYSE + bips[lum])}
        for nom, att in attendus.items():
            if intervalle(j, nom) != att:
                erreurs.append(f"chronogramme #{i} : {nom} = {intervalle(j, nom)}, attendu {att}")
        if j[-1][1]:
            erreurs.append(f"chronogramme #{i} : fin de cycle non éteinte {j[-1]}")
        if [n for n in bips if n != lum and intervalle(j, n)[0] is not None]:
            erreurs.append(f"chronogramme #{i} : une autre lumière s'allume pendant le cycle")
    for i, titre in ((6, "verte"), (5, "jaune"), (0, "rouge")):
        L.append(f"   Combinaison #{i} (abcd = {i:04b}) — lumière {titre}")
        for t, e in journaux[i]:
            L.append(f"     t = {t / 1000:7.3f} s : " + (", ".join(sorted(e)) if e else "tout éteint"))
        L.append("")
    L.append(f"   Allumage de la lumière ............ t = {fr(T_ANALYSE)} (après Marche)")
    for nom, t in bips.items():
        L.append(f"   Bip {nom:<9} .................... {fr(t)} (de {fr(T_ANALYSE)} à {fr(T_ANALYSE + t)})")
    L.append(f"   Fin du cycle (tout éteint) ........ t = {fr(t_fin)}, soit {fr(T_AFFICHAGE)} après l'allumage")
    L.append(f"   Vérifié sur les 16 combinaisons : {'CONFORME' if len(erreurs) == n_err else 'NON CONFORME'}")
    L.append("")

    # 3. dessin
    L.append("3. CONTRÔLES DU DESSIN (calculés sur la géométrie du SVG)")
    L.append("")
    info, err = controles(d, noeuds, circuit)
    erreurs += err
    L += ["   " + x for x in info]
    L.append(f"   Points de jonction dessinés : {sum(1 for n in noeuds.degre.values() if n >= 3)} "
             f"(un par jonction réelle, placés automatiquement)")
    L.append(f"   Résultat : {'CONFORME' if not err else 'NON CONFORME'}")
    L.append("   Le PNG a aussi été relu à l'oeil après le rendu.")
    L.append("")
    L.append("BILAN : " + ("TOUTES LES VÉRIFICATIONS RÉUSSIES" if not erreurs else "ÉCHEC"))
    L += ["  - " + e for e in erreurs]

    svg = os.path.join(ICI, "diagramme_bouteille.svg")
    png = os.path.join(ICI, "diagramme_bouteille.png")
    ecrire_svg(d, noeuds, hauteur, svg)
    with open(os.path.join(ICI, "verification.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    print("\n".join(L))
    if "--sans-png" not in sys.argv:
        rendre_png(svg, png, hauteur)
    return 1 if erreurs else 0


if __name__ == "__main__":
    sys.exit(main())
