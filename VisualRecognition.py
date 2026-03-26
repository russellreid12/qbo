#!/usr/bin/env python3
import importlib
import os
import time
import yaml
import sys








class VisualRecognition:




   def __init__(self, debug=False, tmp_file='/tmp/VisualRecognitionCapture.png', tfvrmodel='/opt/qbo/tfvrmodel',
                faces_dir='/opt/qbo/known_faces'):
       """
       Args:
           debug:       Print verbose output.
           tmp_file:    Path to save the captured image.
           tfvrmodel:   Path to TensorFlow ImageNet model directory.
           faces_dir:   Path to known-faces directory.
                        Structure:
                          /opt/qbo/known_faces/
                            russell.jpg
                            sarah.jpg
                            ...
                        One clear face photo per file. Filename (without extension)
                        becomes the person's display name.
       """
       self.config = yaml.safe_load(open("/opt/qbo/config.yml"))
       self.debug = debug
       self.tmp_file = tmp_file
       self.tfvrmodel = tfvrmodel
       self.faces_dir = faces_dir
       self.results = []
       self.resultsAvailable = False
       self.faceResults = []         # List of recognised name strings
       self.faceResultsAvailable = False




       # Pre-load known face encodings at startup so recognition is fast
       self._known_face_encodings = []
       self._known_face_names = []
       self._loadKnownFaces()








   # ------------------------------------------------------------------
   # Trigger detection
   # ------------------------------------------------------------------




   def askAboutMe(self, text):
       if self.config['language'] == 'spanish':
           texts = ["mira esto", "observa esto", "reconocimiento visual",
                    "inicia reconocimiento visual", "que ves", "que tengo aqui",
                    "quien es", "reconoce cara"]
       else:
           texts = ["watch this", "visual recognition", "start visual recognition",
                    "look this", "what is this", "who is this", "recognize face"]




       for t in texts:
           if text.find(t) != -1:
               return True
       return False








   # ------------------------------------------------------------------
   # Capture helpers
   # ------------------------------------------------------------------




   def captureAndRecognizeImage(self, webcam=None):
       """Capture then run both Gemini object detection and face recognition."""
       self.captureImage(webcam)
       self.recognizeImage()
       self.recognizeFaces()




   def captureAndRecognizeImageGemini(self, webcam=None):
       """Capture then run Gemini object detection only."""
       self.captureImage(webcam)
       try:
           if len(self.config.get('GeminiAPIKey', '')) > 2:
               self.recognizeImageWithGemini()
       except KeyError:
           pass




   def captureImage(self, webcam=None):
       import cv2
       webcamByArg = True




       if webcam is None:
           webcamByArg = False
           webcam = cv2.VideoCapture(int(self.config['camera']), cv2.CAP_V4L2)




       return_value, image = webcam.read()
       cv2.imwrite(self.tmp_file, image)
       del return_value, image




       if webcamByArg is False:
           webcam.release()








   # ------------------------------------------------------------------
   # Object recognition routing
   # ------------------------------------------------------------------




   def recognizeImage(self):
       try:
           if len(self.config.get('GeminiAPIKey', '')) > 2:
               self.recognizeImageWithGemini()
           else:
               self.recognizeImageWithTensorFlow()
       except KeyError:
           self.recognizeImageWithTensorFlow()








   # ------------------------------------------------------------------
   # TensorFlow (ImageNet) — kept as fallback
   # ------------------------------------------------------------------




   def recognizeImageWithTensorFlow(self, num_top_predictions=5):




       self.resultsAvailable = False




       import re
       import numpy as np
       import tensorflow as tf




       model_dir = self.tfvrmodel




       class NodeLookup(object):
           """Converts integer node ID's to human readable labels."""




           def __init__(self, label_lookup_path=None, uid_lookup_path=None):
               if not label_lookup_path:
                   label_lookup_path = os.path.join(
                       model_dir, 'imagenet_2012_challenge_label_map_proto.pbtxt')
               if not uid_lookup_path:
                   uid_lookup_path = os.path.join(
                       model_dir, 'imagenet_synset_to_human_label_map.txt')
               self.node_lookup = self.load(label_lookup_path, uid_lookup_path)




           def load(self, label_lookup_path, uid_lookup_path):
               if not tf.gfile.Exists(uid_lookup_path):
                   tf.logging.fatal('File does not exist %s', uid_lookup_path)
               if not tf.gfile.Exists(label_lookup_path):
                   tf.logging.fatal('File does not exist %s', label_lookup_path)




               proto_as_ascii_lines = tf.gfile.GFile(uid_lookup_path).readlines()
               uid_to_human = {}
               p = re.compile(r'[n\d]*[ \S,]*')
               for line in proto_as_ascii_lines:
                   parsed_items = p.findall(line)
                   uid = parsed_items[0]
                   human_string = parsed_items[2]
                   uid_to_human[uid] = human_string




               node_id_to_uid = {}
               proto_as_ascii = tf.gfile.GFile(label_lookup_path).readlines()
               for line in proto_as_ascii:
                   if line.startswith('  target_class:'):
                       target_class = int(line.split(': ')[1])
                   if line.startswith('  target_class_string:'):
                       target_class_string = line.split(': ')[1]
                       node_id_to_uid[target_class] = target_class_string[1:-2]




               node_id_to_name = {}
               for key, val in node_id_to_uid.items():
                   if val not in uid_to_human:
                       tf.logging.fatal('Failed to locate: %s', val)
                   name = uid_to_human[val]
                   node_id_to_name[key] = name




               return node_id_to_name




           def id_to_string(self, node_id):
               if node_id not in self.node_lookup:
                   return ''
               return self.node_lookup[node_id]




       def create_graph():
           with tf.gfile.FastGFile(os.path.join(model_dir, 'classify_image_graph_def.pb'), 'rb') as f:
               graph_def = tf.GraphDef()
               graph_def.ParseFromString(f.read())
               _ = tf.import_graph_def(graph_def, name='')




       if not tf.gfile.Exists(self.tmp_file):
           tf.logging.fatal('File does not exist %s', self.tmp_file)
       image_data = tf.gfile.FastGFile(self.tmp_file, 'rb').read()




       create_graph()




       with tf.Session() as sess:
           softmax_tensor = sess.graph.get_tensor_by_name('softmax:0')
           predictions = sess.run(softmax_tensor, {'DecodeJpeg/contents:0': image_data})
           predictions = np.squeeze(predictions)




           node_lookup = NodeLookup()




           self.results = []
           top_k = predictions.argsort()[-num_top_predictions:][::-1]




           for node_id in top_k:
               human_string = node_lookup.id_to_string(node_id)
               score = predictions[node_id]
               if self.debug:
                   print('%s (score = %.5f)' % (human_string, score))
               self.results.append(human_string)




           self.resultsAvailable = True








   # ------------------------------------------------------------------
   # Gemini Vision — object / scene detection
   # ------------------------------------------------------------------




   def recognizeImageWithGemini(self):
       """
       Detect objects and scenes using Google Gemini Vision API.




       Requirements:
           pip install google-generativeai Pillow




       config.yml keys:
           GeminiAPIKey: "YOUR_API_KEY_HERE"
           language: "english"   # or "spanish"




       Free API key: https://aistudio.google.com/app/apikey
       """




       self.resultsAvailable = False




       api_key = self.config.get('GeminiAPIKey', '')
       if len(api_key) <= 2:
           print("GeminiAPIKey must be set in config.yml to use Gemini recognition.")
           return




       try:
           import google.generativeai as genai
       except ImportError:
           print("Google Gemini requires: pip install google-generativeai")
           return




       if not os.path.exists(self.tmp_file):
           print(f"Image file does not exist: {self.tmp_file}")
           return




       try:
           import PIL.Image
           genai.configure(api_key=api_key)
           model = genai.GenerativeModel("gemini-1.5-flash")
           image = PIL.Image.open(self.tmp_file)




           lang = self.config.get('language', 'english')
           if lang == 'spanish':
               prompt = (
                   "Observa esta imagen y lista los objetos, personas o elementos principales que ves. "
                   "Devuelve solo una lista de etiquetas cortas separadas por comas, sin explicaciones."
               )
           else:
               prompt = (
                   "Look at this image and list the main objects, people, or elements you can see. "
                   "Return only a comma-separated list of short labels, no explanations."
               )




           response = model.generate_content([prompt, image])
           raw_text = response.text.strip()




           if self.debug:
               print(f"Gemini raw response: {raw_text}")




           labels = [label.strip() for label in raw_text.split(',') if label.strip()]
           self.results = [label for label in labels if len(label) < 60]




           if self.debug:
               for label in self.results:
                   print(f"  - {label}")




           self.resultsAvailable = True




       except Exception as e:
           print(f"Gemini Visual Recognition API error: {e}")
           self.results = []
           self.resultsAvailable = False








   # ------------------------------------------------------------------
   # Face recognition — load known faces
   # ------------------------------------------------------------------




   def _loadKnownFaces(self):
       """
       Load face encodings from self.faces_dir at startup.




       Drop a photo (JPG or PNG) named after the person into the folder:
           /opt/qbo/known_faces/russell.jpg
           /opt/qbo/known_faces/sarah.png




       The filename (without extension) is used as the display name.
       Call reloadKnownFaces() at runtime to pick up newly added photos
       without restarting.
       """
       try:
           import face_recognition
       except ImportError:
           if self.debug:
               print("face_recognition not installed. Run: pip install face-recognition")
           return




       if not os.path.isdir(self.faces_dir):
           if self.debug:
               print(f"Known faces directory not found: {self.faces_dir}  (create it and add photos)")
           return




       self._known_face_encodings = []
       self._known_face_names = []




       supported = ('.jpg', '.jpeg', '.png')
       for filename in os.listdir(self.faces_dir):
           if not filename.lower().endswith(supported):
               continue




           name = os.path.splitext(filename)[0].replace('_', ' ').title()
           path = os.path.join(self.faces_dir, filename)




           try:
               img = face_recognition.load_image_file(path)
               encodings = face_recognition.face_encodings(img)
               if encodings:
                   self._known_face_encodings.append(encodings[0])
                   self._known_face_names.append(name)
                   if self.debug:
                       print(f"Loaded face: {name}")
               else:
                   print(f"Warning: no face detected in {filename}, skipping.")
           except Exception as e:
               print(f"Error loading {filename}: {e}")




       if self.debug:
           print(f"Total known faces loaded: {len(self._known_face_names)}")




   def reloadKnownFaces(self):
       """Reload known faces from disk (call after adding new photos)."""
       self._loadKnownFaces()








   # ------------------------------------------------------------------
   # Face recognition — identify faces in captured image
   # ------------------------------------------------------------------




   def recognizeFaces(self, tolerance=0.55):
       """
       Identify faces in self.tmp_file against known faces.




       Results are stored in self.faceResults as a list of name strings.
       Unknown faces are listed as 'Unknown'.




       Args:
           tolerance: Match strictness (lower = stricter). Default 0.55 works
                      well for Pi camera quality. Range: 0.4 (strict) - 0.65 (loose).




       Requirements:
           pip install face-recognition




       Populates:
           self.faceResults          - list of matched name strings
           self.faceResultsAvailable - True on success
       """




       self.faceResults = []
       self.faceResultsAvailable = False




       try:
           import face_recognition
       except ImportError:
           print("face_recognition not installed. Run: pip install face-recognition")
           return




       if not os.path.exists(self.tmp_file):
           print(f"Image file does not exist: {self.tmp_file}")
           return




       try:
           import numpy as np
           image = face_recognition.load_image_file(self.tmp_file)
           face_locations = face_recognition.face_locations(image)
           face_encodings = face_recognition.face_encodings(image, face_locations)




           if self.debug:
               print(f"Faces detected in image: {len(face_locations)}")




           if not face_encodings:
               if self.debug:
                   print("No faces found in the captured image.")
               self.faceResultsAvailable = True  # Ran successfully, just empty
               return




           for face_encoding in face_encodings:
               name = "Unknown"




               if self._known_face_encodings:
                   distances = face_recognition.face_distance(self._known_face_encodings, face_encoding)
                   best_match_index = int(np.argmin(distances))




                   if distances[best_match_index] <= tolerance:
                       name = self._known_face_names[best_match_index]
                       if self.debug:
                           print(f"  Matched: {name} (distance={distances[best_match_index]:.3f})")
                   else:
                       if self.debug:
                           print(f"  Unknown face (closest distance={distances[best_match_index]:.3f})")
               else:
                   if self.debug:
                       print("  No known faces loaded - all faces will be Unknown.")




               self.faceResults.append(name)




           self.faceResultsAvailable = True




       except Exception as e:
           print(f"Face recognition error: {e}")
           self.faceResults = []
           self.faceResultsAvailable = False




   def getCombinedResults(self):
       """
       Return a merged summary of object detection + face recognition.




       Returns:
           dict with keys:
               'objects' - list of Gemini/TF labels
               'faces'   - list of identified names
               'summary' - human-readable string combining both
       """
       objects = self.results if self.resultsAvailable else []
       faces = self.faceResults if self.faceResultsAvailable else []




       lang = self.config.get('language', 'english')




       if lang == 'spanish':
           face_str = ("Personas reconocidas: " + ", ".join(faces)) if faces else "No se detectaron caras."
           obj_str = ("Objetos detectados: " + ", ".join(objects)) if objects else "No se detectaron objetos."
       else:
           face_str = ("People recognised: " + ", ".join(faces)) if faces else "No faces detected."
           obj_str = ("Objects detected: " + ", ".join(objects)) if objects else "No objects detected."




       return {
           'objects': objects,
           'faces': faces,
           'summary': f"{face_str} {obj_str}"
       }








# ----------------------------------------------------------------------
# CLI test
# ----------------------------------------------------------------------




if __name__ == '__main__':




   vc = VisualRecognition(debug=True)




   while True:
       input('\nPress Enter to capture or CTRL+C to close.')




       print("Photo in ", end="")
       for i in [3, 2, 1]:
           print(i, end=" ")
           sys.stdout.flush()
           time.sleep(1)




       vc.captureImage()
       print("TAKEN!\n")




       print("--- Gemini Object Detection ---")
       vc.recognizeImageWithGemini()




       print("\n--- Face Recognition ---")
       vc.recognizeFaces()




       print("\n--- Combined Results ---")
       combined = vc.getCombinedResults()
       print(combined['summary'])
       print()











