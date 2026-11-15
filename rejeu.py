"""Client de relecture : rejoue les réponses RÉELLES du modèle (Amazon Bedrock) enregistrées dans une trace.
Les outils Python sont ré-exécutés pour de vrai ; seules les réponses du modèle viennent de la trace."""
import json, time, glob
class ClientRejeu:
    def __init__(self, dossier, vitesse=float(__import__("os").environ.get("REJEU_VITESSE", "0.35"))):
        self.par_demande = {}
        for f in glob.glob(f"{dossier}/traces/*.json"):
            d = json.load(open(f, encoding="utf-8"))
            self.par_demande.setdefault((d["persona"], d["demande"]), f)
        self.vitesse = vitesse; self.file = None
    def choisir(self, fichier):
        self.fichier = fichier
        d = json.load(open(fichier, encoding="utf-8"))
        E = d["trace"]["etapes"]; tours = []
        for i, e in enumerate(E):
            if e["type"] != "modele": continue
            suite = []
            for x in E[i+1:]:
                if x["type"] == "modele": break
                suite.append(x)
            if suite and suite[0]["type"] == "controle":
                contenu = [{"toolUse": {"toolUseId": f"r{i}", "name": "rediger_avis", "input": suite[0]["avis_propose"]}}]
            else:
                contenu = [{"toolUse": {"toolUseId": f"r{i}_{k}", "name": x["outil"], "input": x["entree"]}}
                           for k, x in enumerate(suite) if x["type"] == "outil"]
            tours.append((contenu, e.get("request_id"), e.get("duree_s", 2)))
        self.file = tours
        self.dernier = next((x for x in reversed(tours) if x[0] and x[0][0]["toolUse"]["name"] == "rediger_avis"), tours[-1])
    def converse(self, **kw):
        if len(kw.get("messages", [])) == 1 and getattr(self, "fichier", None):
            self.choisir(self.fichier)
        if self.file is None:
            raise RuntimeError("aucune trace choisie")
        if not self.file:   # trace épuisée : on redonne le dernier avis enregistré
            self.file = [self.dernier]
        contenu, rid, duree = self.file.pop(0)
        time.sleep(min(duree, 6) * self.vitesse)
        return {"output": {"message": {"role": "assistant", "content": contenu}}, "stopReason": "tool_use",
                "usage": {"inputTokens": 0, "outputTokens": 0}, "ResponseMetadata": {"RequestId": rid}}
