class LabelManager:
    def __init__(self):
        self.bboxes = []

    def add(self,bbox):
        self.bboxes.append(bbox)

    def remove(self,bbox_id):
        self.bboxes=[b for b in self.bboxes if b.id !=bbox_id]

    def clear(self):
        self.bboxes.clear()