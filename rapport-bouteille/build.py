#!/usr/bin/env python3
"""Construit le rapport dans le .docx fourni (la page couverture et les propriétés restent intactes).

Usage : python3 build.py <dossier_unpacked_original> <dossier_sortie> [pages.json]
"""
import json
import os
import re
import shutil
import sys
from xml.sax.saxutils import escape

SRC, OUT = sys.argv[1], sys.argv[2]
PAGES = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}

if os.path.exists(OUT):
    shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)
W = os.path.join(OUT, "word")

TEXT_W = 9406  # largeur utile (twips) avec les marges de la section 2
EMU_IN = 914400

# ------------------------------------------------------------------ helpers
_bm = [100]
_pic = [500]
heads = []  # (niveau, texte, bookmark)


def r(text, b=False, i=False, hl=False, sz=None, color=None):
    pr = ""
    if b:
        pr += "<w:b/>"
    if i:
        pr += "<w:i/>"
    if color:
        pr += f'<w:color w:val="{color}"/>'
    if sz:
        pr += f'<w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/>'
    if hl:
        pr += '<w:highlight w:val="yellow"/>'
    pr = f"<w:rPr>{pr}</w:rPr>" if pr else ""
    return f'<w:r>{pr}<w:t xml:space="preserve">{escape(text)}</w:t></w:r>'


def runs(spec):
    """spec : str, ou liste de str / tuples (texte, dict d'options)."""
    if isinstance(spec, str):
        return r(spec)
    out = ""
    for s in spec:
        out += r(s) if isinstance(s, str) else r(s[0], **s[1])
    return out


def p(spec="", style=None, jc=None, extra_ppr="", keep=False):
    ppr = ""
    if style:
        ppr += f'<w:pStyle w:val="{style}"/>'
    if keep:
        ppr += "<w:keepNext/>"
    ppr += extra_ppr
    if jc:
        ppr += f'<w:jc w:val="{jc}"/>'
    ppr = f"<w:pPr>{ppr}</w:pPr>" if ppr else ""
    return f"<w:p>{ppr}{runs(spec)}</w:p>"


def h(level, text):
    _bm[0] += 1
    name = f"_Toc{_bm[0]:08d}"
    heads.append((level, text, name))
    bid = _bm[0]
    return (f'<w:p><w:pPr><w:pStyle w:val="Heading{level}"/></w:pPr>'
            f'<w:bookmarkStart w:id="{bid}" w:name="{name}"/>{r(text)}'
            f'<w:bookmarkEnd w:id="{bid}"/></w:p>')


def bullets(items, num=1):
    return "".join(
        f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="0"/>'
        f'<w:numId w:val="{num}"/></w:numPr></w:pPr>{runs(it)}</w:p>' for it in items)


def image(rid, w_in, h_in, crop=None):
    _pic[0] += 1
    cx, cy = int(w_in * EMU_IN), int(h_in * EMU_IN)
    src = ""
    if crop:
        src = '<a:srcRect ' + " ".join(f'{k}="{v}"' for k, v in crop.items()) + "/>"
    return (
        '<w:p><w:pPr><w:keepNext/><w:spacing w:after="60"/><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:noProof/></w:rPr><w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        '<wp:effectExtent l="0" t="0" r="0" b="0"/>'
        f'<wp:docPr id="{_pic[0]}" name="Image {_pic[0]}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        '<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:nvPicPr><pic:cNvPr id="{_pic[0]}" name=""/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/>{src}<a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        '<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
        '</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')


def caption(text):
    return p(text, style="Caption", jc="center")


def cell(content, width, shade=None, bold=False, jc="center", vmerge=None):
    tcpr = f'<w:tcW w:w="{width}" w:type="dxa"/>'
    if shade:
        tcpr += f'<w:shd w:val="clear" w:color="auto" w:fill="{shade}"/>'
    tcpr += '<w:vAlign w:val="center"/>'
    paras = content if isinstance(content, list) else [content]
    body = ""
    for c in paras:
        if isinstance(c, str) and c.startswith("<m:oMath"):
            body += f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/><w:jc w:val="{jc}"/></w:pPr>{c}</w:p>'
        else:
            spec = [(c, {"b": True})] if (bold and isinstance(c, str)) else c
            body += (f'<w:p><w:pPr><w:spacing w:before="40" w:after="40" w:line="240" w:lineRule="auto"/>'
                     f'<w:jc w:val="{jc}"/></w:pPr>{runs(spec)}</w:p>')
    return f"<w:tc><w:tcPr>{tcpr}</w:tcPr>{body}</w:tc>"


def table(widths, rows, header_rows=1):
    assert sum(widths) <= TEXT_W, sum(widths)
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = (f'<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:w="{sum(widths)}" w:type="dxa"/>'
           f'<w:jc w:val="center"/><w:tblLayout w:type="fixed"/><w:tblLook w:val="04A0" w:firstRow="1" w:lastRow="0" w:firstColumn="1" w:lastColumn="0" w:noHBand="0" w:noVBand="1"/></w:tblPr>'
           f'<w:tblGrid>{grid}</w:tblGrid>')
    for k, row in enumerate(rows):
        trpr = "<w:trPr><w:cantSplit/>" + ("<w:tblHeader/>" if k < header_rows else "") + "</w:trPr>"
        cells = "".join(row)
        if k < len(rows) - 1:  # garder le tableau entier sur une page
            cells = cells.replace("<w:pPr><w:spacing", "<w:pPr><w:keepNext/><w:spacing")
        out += f"<w:tr>{trpr}{cells}</w:tr>"
    return out + "</w:tbl>" + p("", extra_ppr='<w:spacing w:after="0"/>')


# --------------------------------------------------- équations (Office Math)
def mvar(v):
    # variable barrée : lettre(s) + barre combinante U+0305 sur chaque caractère
    if v.startswith("/"):
        return "".join(ch + "̅" for ch in v[1:])
    return v


def mexpr(name, terms):
    """terms : liste de termes, chaque terme = liste de variables ('/a' = a barre)."""
    out = f"{name} = " if name and name != "+" else ("+ " if name == "+" else "")
    return out + "  +  ".join("·".join(mvar(v) for v in t) for t in terms)


def math_para(name, terms):
    return p([(mexpr(name, terms), {"sz": 28})], jc="center",
             extra_ppr='<w:spacing w:before="120" w:after="200"/>')


def math_inline(name, terms):
    return mexpr(name, terms)


V_T = [["/a", "b", "c", "/d"]]
J_T = [["/a", "b", "/c", "d"], ["a", "/b", "c", "/d"]]
R_T = [["/a", "/b"], ["a", "b"], ["/c", "/d"], ["c", "d"], ["a", "/c"]]


def renomme(terms):
    m = {"a": "c1", "b": "c2", "c": "f1", "d": "f2"}
    return [[("/" if v.startswith("/") else "") + m[v.lstrip("/")] for v in t] for t in terms]


# ------------------------------------------------------- simulation logique
def eval_terms(terms, bits):
    val = dict(zip("abcd", bits))
    return int(any(all((1 - val[v[1]]) if v.startswith("/") else val[v] for v in t) for t in terms))


# ==================================================================== contenu
B = []  # corps (après la page couverture)

# ---------- table des matières
B.append(p("Table des matières", style="TOCHeading"))
B.append("@@TOC@@")

# ---------- 1. Introduction
B.append(h(1, "1. Introduction"))
B.append(p("Dans le cadre du cours Automatismes industriels, j’ai été mandaté pour concevoir le prototype "
           "d’une machine qui vérifie si l’étiquette est bien placée sur une bouteille de jus. Si le prototype "
           "fonctionne bien, il pourra être adapté à la ligne de remplissage principale de l’usine. La "
           "programmation du système doit être faite dans Automation Studio."))
B.append(p("Ce rapport présente la démarche que j’ai suivie. Je commence par le cahier des charges, qui "
           "résume le problème et ce que la machine doit faire. Ensuite, je définis les entrées et les sorties "
           "du système, je construis la table de vérité et je simplifie les équations de chaque lumière avec "
           "des tables de Karnaugh. Pour finir, j’explique les réflexions qui m’ont guidé pour concevoir le "
           "circuit à contacts dans Automation Studio."))

# ---------- 2. Cahier des charges
B.append(h(1, "2. Cahier des charges"))
B.append(h(2, "2.1 Mise en situation"))
B.append(p("Sur une ligne de remplissage, une étiquette mal placée donne un produit qui ne peut pas être vendu. "
           "Il faut donc une machine capable de vérifier automatiquement la position de l’étiquette et "
           "d’avertir l’opérateur du résultat. Bobby, le concepteur, a décidé de réutiliser de vieux capteurs "
           "pour fabriquer le système. Comme ces capteurs sont recyclés, il faut aussi prévoir le cas où un "
           "capteur donne une lecture qui n’a pas de sens."))
B.append(h(2, "2.2 But du système"))
B.append(p("Le but est de concevoir un circuit qui, après l’appui sur le bouton « Marche », lit quatre "
           "capteurs placés à différentes hauteurs sur la bouteille et indique le résultat à l’opérateur avec "
           "un voyant lumineux et un signal sonore :"))
B.append(bullets([["Position bonne → ", ("lumière verte", {"b": True})],
                  ["Position non conforme → ", ("lumière jaune", {"b": True})],
                  ["Erreur du système → ", ("lumière rouge", {"b": True})]]))
B.append(h(2, "2.3 Fonctionnement demandé"))
B.append(p("Le cycle de test se déroule de la façon suivante :"))
B.append(bullets([
    "L’opérateur appuie sur le bouton-poussoir « Marche » pour démarrer un cycle de test.",
    "Après un délai, les capteurs font l’analyse et la lumière correspondant au résultat s’allume.",
    "Un temporisateur garde la lumière allumée assez longtemps pour que l’opérateur voie le résultat.",
    "En même temps, un signal sonore fait un bip dont la durée dépend du résultat.",
]))
B.append(p("Les délais sont différents pour chaque étudiant. Voici les valeurs de mon devoir :", keep=True))
TW = [6206, 2400]
B.append(table(TW, [
    [cell("Paramètre", TW[0], "D9D9D9", True), cell("Valeur", TW[1], "D9D9D9", True)],
    [cell("Délai entre l’appui sur Marche et l’analyse des capteurs", TW[0], jc="left"), cell("3,173 s", TW[1])],
    [cell("Durée d’affichage des lumières", TW[0], jc="left"), cell("9,757 s", TW[1])],
    [cell("Bip – position bonne (lumière verte)", TW[0], jc="left"), cell("1,35 s", TW[1])],
    [cell("Bip – position non conforme (lumière jaune)", TW[0], jc="left"), cell("2,7 s", TW[1])],
    [cell("Bip – erreur du système (lumière rouge)", TW[0], jc="left"), cell("4,05 s", TW[1])],
]))
B.append(p("Tableau 1 – Temporisations du système", style="Caption", jc="center"))
B.append(h(2, "2.4 Contraintes"))
B.append(bullets([
    "Quatre capteurs, a, b, c et d, détectent la position de l’étiquette.",
    "Pour être bien positionnée, l’étiquette doit être détectée par les capteurs b et c, sans atteindre "
    "les niveaux a et d (a = 0, b = 1, c = 1, d = 0).",
    "À cause de leur position, il est physiquement impossible que les capteurs a et b, ou c et d, "
    "détectent en même temps.",
    "La table de vérité ne doit pas inclure le bouton Marche, le signal sonore ni les temporisateurs.",
    "Le circuit doit être réalisé dans Automation Studio à partir du fichier de départ.",
]))

# ---------- 3. Entrées / sorties
B.append(h(1, "3. Définition des entrées et des sorties"))
B.append(p("Dans mes brouillons, j’ai noté les capteurs c1, c2, f1 et f2. La correspondance avec les lettres "
           "de l’énoncé est la suivante : a = c1, b = c2, c = f1 et d = f2. Dans ce rapport, j’utilise les "
           "lettres a, b, c et d. Pour un capteur, la valeur 1 veut dire qu’il détecte l’étiquette et la valeur "
           "0 qu’il ne la détecte pas."))
EW = [1500, 1700, 2706, 3500]
B.append(p("Entrées", style="Heading3"))
B.append(table(EW, [
    [cell(x, w, "D9D9D9", True) for x, w in zip(["Variable", "Brouillon", "Élément", "Description"], EW)],
    [cell("a", EW[0]), cell("c1", EW[1]), cell("Capteur a (Capta)", EW[2], jc="left"),
     cell("1 = étiquette détectée au niveau a", EW[3], jc="left")],
    [cell("b", EW[0]), cell("c2", EW[1]), cell("Capteur b (Captb)", EW[2], jc="left"),
     cell("1 = étiquette détectée au niveau b", EW[3], jc="left")],
    [cell("c", EW[0]), cell("f1", EW[1]), cell("Capteur c (Captc)", EW[2], jc="left"),
     cell("1 = étiquette détectée au niveau c", EW[3], jc="left")],
    [cell("d", EW[0]), cell("f2", EW[1]), cell("Capteur d (Captd)", EW[2], jc="left"),
     cell("1 = étiquette détectée au niveau d", EW[3], jc="left")],
    [cell("M", EW[0]), cell("Marche", EW[1]), cell("Bouton-poussoir NO (BoutonMarche)", EW[2], jc="left"),
     cell("Démarre un cycle de test (hors table de vérité)", EW[3], jc="left")],
]))
B.append(p("Tableau 2 – Entrées du système", style="Caption", jc="center"))
B.append(p("Sorties", style="Heading3"))
SW = [1500, 3406, 4500]
B.append(table(SW, [
    [cell(x, w, "D9D9D9", True) for x, w in zip(["Variable", "Élément", "Description"], SW)],
    [cell("V", SW[0]), cell("Voyant vert (LumVert)", SW[1], jc="left"),
     cell("Étiquette en bonne position", SW[2], jc="left")],
    [cell("J", SW[0]), cell("Voyant jaune (LumJaune)", SW[1], jc="left"),
     cell("Étiquette non conforme", SW[2], jc="left")],
    [cell("R", SW[0]), cell("Voyant rouge (LumRouge)", SW[1], jc="left"),
     cell("Erreur du système", SW[2], jc="left")],
    [cell("Son", SW[0]), cell("Avertisseur sonore (SonHautParleur)", SW[1], jc="left"),
     cell("Bip de 1,35 s, 2,7 s ou 4,05 s selon le résultat (hors table de vérité)", SW[2], jc="left")],
]))
B.append(p("Tableau 3 – Sorties du système", style="Caption", jc="center"))

# ---------- 4. Table de vérité
B.append(h(1, "4. Table de vérité"))
B.append(p("Avec quatre capteurs, il y a 2⁴ = 16 combinaisons possibles. Pour remplir la table, j’ai suivi "
           "cette logique :"))
B.append(bullets([
    [("Verte : ", {"b": True}), "seulement la combinaison de bonne position, abcd = 0110 (ligne 6)."],
    [("Jaune : ", {"b": True}), "l’étiquette touche deux capteurs voisins, mais elle est décalée vers le "
     "niveau d (0101, ligne 5) ou vers le niveau a (1010, ligne 10)."],
    [("Rouge : ", {"b": True}), "toutes les autres combinaisons. Elles ne correspondent à aucune position "
     "réelle de l’étiquette, ou bien elles sont physiquement impossibles (a et b ou c et d en même temps). "
     "Si elles arrivent, c’est qu’un capteur fonctionne mal."],
]))
TV = [700, 650, 650, 650, 650, 750, 750, 750, 3856]
fills = {"V": "C6EFCE", "J": "FFEB9C", "R": "FFC7CE"}
rows = [[cell(x, w, "D9D9D9", True) for x, w in zip(["#", "a", "b", "c", "d", "V", "J", "R", "Résultat"], TV)]]
for n in range(16):
    bits = [(n >> k) & 1 for k in (3, 2, 1, 0)]
    a, b_, c, d = bits
    v, j, rr = eval_terms(V_T, bits), eval_terms(J_T, bits), eval_terms(R_T, bits)
    assert v + j + rr == 1
    if v:
        res = "Bonne position"
    elif j:
        res = "Non conforme (décalée vers " + ("d)" if d else "a)")
    elif (a and b_) or (c and d):
        res = "Erreur : combinaison impossible"
    elif n == 0:
        res = "Erreur : aucune détection"
    else:
        res = "Erreur : lecture incohérente"
    row = [cell(str(n), TV[0])] + [cell(str(x), w) for x, w in zip(bits, TV[1:5])]
    for k, (key, val) in enumerate((("V", v), ("J", j), ("R", rr))):
        row.append(cell(str(val), TV[5 + k], fills[key] if val else None, bold=bool(val)))
    row.append(cell(res, TV[8], jc="left"))
    rows.append(row)
B.append(table(TV, rows))
B.append(p("Tableau 4 – Table de vérité du système", style="Caption", jc="center"))
B.append(p("J’ai d’abord fait la table de vérité à la main (figure 1) avant de la recopier au propre dans le "
           "tableau 4. On remarque qu’il y a toujours une seule lumière allumée par combinaison : jamais "
           "aucune, et jamais deux en même temps."))
# image4 : table manuscrite (rognage d'origine conservé)
B.append(image("rId13", 3.0, 3.0 * 1552.2 / 1175.5, {"l": "27302", "t": "6940", "r": "23474"}))
B.append(caption("Figure 1 – Table de vérité faite à la main (brouillon)"))

# ---------- 5. Karnaugh
B.append(h(1, "5. Simplification avec les tables de Karnaugh"))
B.append(p("J’ai fait une table de Karnaugh pour chaque lumière. Les lignes représentent les capteurs a et b "
           "(c1 c2) et les colonnes représentent les capteurs c et d (f1 f2). Les lignes et les colonnes sont "
           "placées dans l’ordre 00, 01, 11, 10 (code Gray), pour que deux cases voisines ne changent que "
           "d’une seule variable. On peut ensuite regrouper les 1 voisins par groupes de 2, 4 ou 8 pour "
           "éliminer des variables."))
B.append(h(2, "5.1 Lumière verte"))
B.append(p("La table de la lumière verte contient un seul 1, dans la case a b = 01 et c d = 10. Comme il n’a "
           "aucun voisin, aucun regroupement n’est possible et l’équation garde les quatre variables :"))
B.append(math_para("V", V_T))
B.append(image("rId12", 2.75, 2.75 * 1668 / 1453))
B.append(caption("Figure 2 – Table de Karnaugh de la lumière verte"))
B.append(h(2, "5.2 Lumière jaune"))
B.append(p("La table de la lumière jaune contient deux 1 : la case 01/01 (abcd = 0101) et la case 10/10 "
           "(abcd = 1010). Ces deux cases ne sont pas voisines, donc on ne peut pas les regrouper. Chaque 1 "
           "donne un terme de quatre variables :"))
B.append(math_para("J", J_T))
B.append(image("rId10", 3.4, 3.4 * 1650 / 1764))
B.append(caption("Figure 3 – Table de Karnaugh de la lumière jaune"))
B.append(h(2, "5.3 Lumière rouge"))
B.append(p("La lumière rouge s’allume pour 13 combinaisons sur 16. J’ai pu faire cinq regroupements de quatre "
           "cases, identifiés par des couleurs sur la figure 4 :"))
GW = [1500, 4906, 3000]
B.append(table(GW, [
    [cell(x, w, "D9D9D9", True) for x, w in zip(["Couleur", "Cases regroupées", "Terme"], GW)],
    [cell("Bleu", GW[0]), cell("Ligne a b = 00", GW[1], jc="left"),
     cell(math_inline("", [["/a", "/b"]]), GW[2])],
    [cell("Jaune", GW[0]), cell("Ligne a b = 11", GW[1], jc="left"),
     cell(math_inline("", [["a", "b"]]), GW[2])],
    [cell("Vert", GW[0]), cell("Colonne c d = 00", GW[1], jc="left"),
     cell(math_inline("", [["/c", "/d"]]), GW[2])],
    [cell("Rouge", GW[0]), cell("Colonne c d = 11", GW[1], jc="left"),
     cell(math_inline("", [["c", "d"]]), GW[2])],
    [cell("Rose", GW[0]), cell("Carré : lignes 11 et 10, colonnes 00 et 01", GW[1], jc="left"),
     cell(math_inline("", [["a", "/c"]]), GW[2])],
]))
B.append(p("Tableau 5 – Regroupements de la lumière rouge", style="Caption", jc="center"))
B.append(p("Les cinq groupes couvrent tous les 1 de la table. Certaines cases font partie de plus d’un groupe, "
           "ce qui est permis avec Karnaugh. L’équation simplifiée est :", keep=True))
B.append(math_para("R", R_T))
B.append(image("rId11", 4.6, 4.6 * 1452.4 / 2028.6,
               {"l": "10304", "t": "10795", "r": "4745", "b": "2127"}))
B.append(caption("Figure 4 – Table de Karnaugh de la lumière rouge et ses regroupements"))
B.append(h(2, "5.4 Résumé des équations"))
QW = [1600, 7806]
B.append(table(QW, [
    [cell(x, w, "D9D9D9", True) for x, w in zip(["Sortie", "Équation simplifiée"], QW)],
    [cell("V", QW[0], fills["V"], True), cell(math_inline("", V_T), QW[1])],
    [cell("J", QW[0], fills["J"], True), cell(math_inline("", J_T), QW[1])],
    [cell("R", QW[0], fills["R"], True), cell(math_inline("", R_T), QW[1])],
]))
B.append(p("Tableau 6 – Équations simplifiées des trois lumières", style="Caption", jc="center"))
B.append(p("Pour vérifier mes équations, je les ai recalculées pour les 16 combinaisons : elles donnent "
           "exactement la même chose que la table de vérité (tableau 4)."))

# ---------- 6. Réflexions pour la conception du circuit
B.append(h(1, "6. Réflexions pour la conception du circuit"))
B.append(h(2, "6.1 Séquence de fonctionnement"))
B.append(p("Avant de dessiner le circuit, j’ai fait un croquis de la séquence dans le temps (figure 5) pour "
           "savoir quels relais et quelles temporisations seraient nécessaires."))
B.append(image("rId14", 6.0, 6.0 * 861 / 2088))
B.append(caption("Figure 5 – Croquis de la séquence de fonctionnement"))
CW = [2200, 7206]
B.append(table(CW, [
    [cell("Temps", CW[0], "D9D9D9", True), cell("Ce qui se passe", CW[1], "D9D9D9", True)],
    [cell("t = 0 s", CW[0]), cell("Appui sur Marche : le cycle démarre et reste en mémoire.", CW[1], jc="left")],
    [cell("t = 3,173 s", CW[0]), cell("Analyse des capteurs : une lumière s’allume et le bip commence.", CW[1], jc="left")],
    [cell("t = 4,523 s", CW[0]), cell("Fin du bip si la lumière est verte (1,35 s).", CW[1], jc="left")],
    [cell("t = 5,873 s", CW[0]), cell("Fin du bip si la lumière est jaune (2,7 s).", CW[1], jc="left")],
    [cell("t = 7,223 s", CW[0]), cell("Fin du bip si la lumière est rouge (4,05 s).", CW[1], jc="left")],
    [cell("t = 12,93 s", CW[0]), cell("Fin du temps d’affichage (9,757 s après l’allumage) : tout s’éteint.", CW[1], jc="left")],
]))
B.append(p("Tableau 7 – Chronologie d’un cycle de test", style="Caption", jc="center"))

B.append(h(2, "6.2 Mémoire du cycle (automaintien)"))
B.append(p("Le bouton Marche est un bouton-poussoir : il revient à sa position dès que l’opérateur le relâche. "
           "Pour que le cycle continue, j’ai utilisé un relais « Automaintient ». Un contact NO de ce relais est "
           "branché en parallèle avec le bouton, ce qui garde la bobine alimentée après le relâchement. Pour "
           "arrêter le cycle à la fin, j’ai placé en série un contact NF temporisé du relais « Affichage lum » : "
           "il s’ouvre après 9,757 s et coupe l’automaintien, ce qui remet tout le circuit à zéro."))
B.append(h(2, "6.3 Temporisations"))
B.append(bullets([
    [("Analyse (3,173 s) : ", {"b": True}), "ce relais est alimenté dès que le cycle démarre. Son contact "
     "temporisé à la fermeture se ferme seulement après 3,173 s, ce qui crée le délai avant l’analyse."],
    [("Affichage lum (9,757 s) : ", {"b": True}), "ce relais commence à compter seulement quand l’analyse est "
     "faite. Son contact temporisé à l’ouverture détermine combien de temps les lumières restent allumées."],
]))
B.append(h(2, "6.4 Logique des lumières"))
B.append(p("Pour passer des équations au schéma à contacts, j’ai utilisé les règles de base :"))
B.append(bullets([
    "un ET (·) correspond à des contacts placés en série ;",
    "un OU (+) correspond à des branches placées en parallèle ;",
    "une variable barrée correspond à un contact normalement fermé (NF), et une variable normale à un "
    "contact normalement ouvert (NO).",
]))
B.append(p("Chaque terme d’une équation devient donc une branche. La lumière verte a une seule branche de "
           "quatre contacts, la lumière jaune a deux branches en parallèle et la lumière rouge en a cinq. Les "
           "trois échelons des lumières sont alimentés par une barre commune, que j’ai appelée « Résultat ». "
           "Cette barre passe par un contact de l’automaintien et par le contact temporisé de l’analyse, ce qui "
           "empêche les lumières de s’allumer avant 3,173 s et les éteint à la fin du cycle."))
B.append(h(2, "6.5 Signal sonore"))
B.append(p("Il n’y a qu’un seul avertisseur, mais la durée du bip doit changer selon la lumière. J’ai donc fait "
           "trois branches en parallèle devant la bobine « SonHautParleur ». Chaque branche contient un contact "
           "NO de la lumière (le son démarre quand elle s’allume) et un contact NF temporisé de la même lumière, "
           "qui s’ouvre après 1,35 s, 2,7 s ou 4,05 s pour arrêter le bip."))
B.append(h(2, "6.6 Combinaisons impossibles"))
B.append(p("Les combinaisons où a et b, ou c et d, sont actifs en même temps sont physiquement impossibles. "
           "J’aurais pu les traiter comme des cas indifférents (X) dans Karnaugh pour simplifier encore plus. "
           "J’ai plutôt choisi d’allumer la lumière rouge dans ces cas-là : comme les capteurs sont recyclés, "
           "une de ces combinaisons voudrait dire qu’un capteur est défectueux, et c’est exactement ce que "
           "l’erreur du système doit signaler."))
B.append(h(2, "6.7 Circuit dans Automation Studio"))
B.append(p("La figure 6 montre le circuit final réalisé dans Automation Studio."))
B.append(p([("[Insérer ici la capture d’écran du circuit fait dans Automation Studio]", {"hl": True})], jc="center",
           extra_ppr='<w:spacing w:before="600" w:after="600"/>'))
B.append(caption("Figure 6 – Circuit à contacts réalisé dans Automation Studio"))
B.append(p([("[À compléter après les tests : par exemple, j’ai testé les combinaisons 0110, 0101, 1010 et "
             "quelques combinaisons d’erreur, et j’ai vérifié les délais avec la simulation.]", {"hl": True})]))

# ---------- 7. Conclusion
B.append(h(1, "7. Conclusion"))
B.append(p("Ce laboratoire m’a permis de suivre toutes les étapes de la conception d’un système combinatoire : "
           "partir d’un problème réel, définir les entrées et les sorties, construire la table de vérité, "
           "simplifier les équations avec Karnaugh et finalement traduire ces équations en circuit à contacts. "
           "La logique des lumières est combinatoire, mais le cycle complet demandait aussi une mémoire "
           "(l’automaintien) et plusieurs temporisations, ce qui a été la partie la plus demandante de la "
           "conception."))
B.append(p([("[À compléter : difficultés rencontrées, ce que tu as appris, améliorations possibles.]", {"hl": True})]))

# ============================================================ TOC
def toc_xml():
    out = ('<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/>'
           '<w:docPartUnique/></w:docPartObj></w:sdtPr><w:sdtContent>')
    first = True
    for lvl, text, bm in heads:
        pg = str(PAGES.get(bm, ""))
        fld_begin = ""
        if first:
            fld_begin = ('<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                         '<w:r><w:instrText xml:space="preserve"> TOC \\o "1-2" \\h \\z \\u </w:instrText></w:r>'
                         '<w:r><w:fldChar w:fldCharType="separate"/></w:r>')
            first = False
        out += (f'<w:p><w:pPr><w:pStyle w:val="TOC{lvl}"/><w:tabs><w:tab w:val="right" w:leader="dot" w:pos="{TEXT_W}"/></w:tabs></w:pPr>'
                f'{fld_begin}<w:hyperlink w:anchor="{bm}" w:history="1">'
                f'<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r><w:r><w:tab/></w:r>'
                f'<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                f'<w:r><w:instrText xml:space="preserve"> PAGEREF {bm} \\h </w:instrText></w:r>'
                f'<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>{pg}</w:t></w:r>'
                f'<w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink></w:p>')
    out += '<w:p><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>'
    return out


body_new = "".join(B).replace("@@TOC@@", toc_xml())

# ============================================================ document.xml
doc_path = os.path.join(W, "document.xml")
doc = open(doc_path, encoding="utf-8").read()
# garder la page couverture : tout jusqu'au paragraphe qui porte le sectPr de la section 1
cut = doc.index("</w:sectPr></w:pPr>")
cut = doc.index("</w:p>", cut) + len("</w:p>")
head = doc[:cut]
final_sect = re.search(r"<w:sectPr w:rsidR=\"008468AF\">.*?</w:sectPr>", doc).group(0)
final_sect = final_sect.replace('<w:sectPr w:rsidR="008468AF">',
                                '<w:sectPr w:rsidR="008468AF"><w:footerReference w:type="default" r:id="rIdFtr1"/>')
final_sect = final_sect.replace("<w:cols", '<w:pgNumType w:start="1"/><w:cols')
doc = head + body_new + final_sect + "</w:body></w:document>"
open(doc_path, "w", encoding="utf-8").write(doc)

# ============================================================ footer
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
open(os.path.join(W, "footer1.xml"), "w", encoding="utf-8").write(
    f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:ftr {NS}>'
    '<w:p><w:pPr><w:pStyle w:val="Footer"/><w:jc w:val="right"/></w:pPr>'
    '<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r>'
    '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>'
    '</w:p></w:ftr>')
rels_p = os.path.join(W, "_rels", "document.xml.rels")
rels = open(rels_p, encoding="utf-8").read()
rels = rels.replace("</Relationships>",
                    '<Relationship Id="rIdFtr1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/></Relationships>')
open(rels_p, "w", encoding="utf-8").write(rels)
ct_p = os.path.join(OUT, "[Content_Types].xml")
ct = open(ct_p, encoding="utf-8").read()
ct = ct.replace("</Types>", '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/></Types>')
open(ct_p, "w", encoding="utf-8").write(ct)

# ============================================================ numbering (puces)
num_p = os.path.join(W, "numbering.xml")
num = open(num_p, encoding="utf-8").read()
bullet = ('<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="hybridMultilevel"/>'
          '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val=""/>'
          '<w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>'
          '<w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol" w:hint="default"/></w:rPr></w:lvl></w:abstractNum>'
          '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num>')
num = num.rstrip()
assert num.endswith("/>"), "numbering.xml : racine non auto-fermante inattendue"
num = num[:-2] + ">" + bullet + "</w:numbering>"  # la racine était vide (auto-fermante)
open(num_p, "w", encoding="utf-8").write(num)

# ============================================================ styles
sty_p = os.path.join(W, "styles.xml")
sty = open(sty_p, encoding="utf-8").read()
HEAD_COLOR = "0F4761"
new_styles = f'''
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:pageBreakBefore/><w:spacing w:before="0" w:after="200"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:cstheme="majorBidi"/><w:color w:val="{HEAD_COLOR}"/><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:unhideWhenUsed/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="240" w:after="100"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:rFonts w:asciiTheme="majorHAnsi" w:hAnsiTheme="majorHAnsi" w:eastAsiaTheme="majorEastAsia" w:cstheme="majorBidi"/><w:color w:val="{HEAD_COLOR}"/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="9"/><w:unhideWhenUsed/><w:qFormat/><w:pPr><w:keepNext/><w:keepLines/><w:spacing w:before="200" w:after="80"/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:color w:val="{HEAD_COLOR}"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TOCHeading"><w:name w:val="TOC Heading"/><w:basedOn w:val="Heading1"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:qFormat/><w:pPr><w:pageBreakBefore w:val="0"/><w:outlineLvl w:val="9"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="TOC1"><w:name w:val="toc 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:before="120" w:after="60"/></w:pPr><w:rPr><w:b/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="TOC2"><w:name w:val="toc 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="39"/><w:unhideWhenUsed/><w:pPr><w:spacing w:after="60"/><w:ind w:left="240"/></w:pPr></w:style>
<w:style w:type="character" w:styleId="Hyperlink"><w:name w:val="Hyperlink"/><w:basedOn w:val="DefaultParagraphFont"/><w:uiPriority w:val="99"/><w:unhideWhenUsed/><w:rPr><w:color w:val="467886"/><w:u w:val="single"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Caption"><w:name w:val="caption"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:uiPriority w:val="35"/><w:unhideWhenUsed/><w:qFormat/><w:pPr><w:spacing w:after="240" w:line="240" w:lineRule="auto"/></w:pPr><w:rPr><w:i/><w:iCs/><w:color w:val="404040"/><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:uiPriority w:val="34"/><w:qFormat/><w:pPr><w:spacing w:after="60"/><w:ind w:left="720"/><w:contextualSpacing/></w:pPr></w:style>
<w:style w:type="table" w:styleId="TableGrid"><w:name w:val="Table Grid"/><w:basedOn w:val="TableNormal"/><w:uiPriority w:val="39"/><w:pPr><w:spacing w:after="0" w:line="240" w:lineRule="auto"/></w:pPr><w:tblPr><w:tblBorders><w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideH w:val="single" w:sz="4" w:space="0" w:color="auto"/><w:insideV w:val="single" w:sz="4" w:space="0" w:color="auto"/></w:tblBorders><w:tblCellMar><w:left w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tblCellMar></w:tblPr></w:style>
'''.replace("\n", "")
sty = sty.replace("</w:styles>", new_styles + "</w:styles>")
open(sty_p, "w", encoding="utf-8").write(sty)

json.dump([h_[2] for h_ in heads], open(os.path.join(os.path.dirname(OUT), "heads.json"), "w"))
json.dump([[h_[0], h_[1], h_[2]] for h_ in heads], open(os.path.join(os.path.dirname(OUT), "heads_full.json"), "w"),
          ensure_ascii=False)
print("ok", len(heads), "titres")
