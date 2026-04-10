# -*- coding: utf-8 -*-


"""

@author: 2019-0248 : Clément RACINET

Projet TRAJCENTER

Version serveur : 1.0
Date : 04/09/2024

Description : 
    Le but de ce code est d'envoyer au robot sur requête TCP/IP les points 
    Le code python est serveur et le robot client.
    
"""





"""
##########################################################################

Import des bibliothèques

##########################################################################
"""


#import pour la gestion du système
import os

#import pour la communication / serveur
import socket
import threading
import struct


#import pour la gestion du temps
import time



#import pour la gestion des données
import re #vérification de formalisme
import ast #Abstract Syntax Trees : lecture par lignes de fichier txt
import pandas as pd
import numpy as np






"""
##########################################################################

Fonction de vérification globales

##########################################################################
"""



def IsIPAddress(chaine):
    """
    Vérifie si la chaîne de caractère passée en argument a la forme d'une adresse IP

    Parameters
    ----------
    chaine : TYPE STRING
        Chaine de caractère que l'on souhaite vérifier

    Returns
    -------
    bool
        Renvoie True si la chaîne de caractères a bien la forme d'une adresse IP
        Renvoie False sinon

    """
    if not isinstance(chaine, str):
        return False
    
    # Expression régulière pour vérifier une adresse IP
    pattern = re.compile(r'^(\d{1,3}\.){3}\d{1,3}$')

    # Vérification de la correspondance
    if pattern.match(chaine):
        return True
    else:
        return False






"""
##########################################################################

Créations de Classes 

##########################################################################
"""


class CustomPrinter:
    """
    Classe pour personnaliser et standardiser les print
    """
    def __init__(self, prefix):
        self.prefix = prefix
    
    def print_message(self, message):
        print(f"{self.prefix}: {message} \n\n")
        
    def print_band(self, caract='*'):
        print(50*str(caract))
    
    def print_error(self, message):
        print('\n')
        self.print_band('!')
        print(f"ERROR: {self.prefix}: {message}")
        self.print_band('!')
        print('\n')
        
    def print_warning(self, message):
        print(f"WARNING: {self.prefix}: {message} \n")





class TCPServer:
    """
    Classe serveur
    """
    def __init__(self, host, port, timeout=np.inf, printer=None):
        self.host = host #ip
        self.port = port 
        self.timeout = timeout
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = [] #memoire des connexions
        self.last_activity_time = time.time() 
        self.is_running = False
        self.timeout_thread = threading.Thread(target=self.check_timeout_thread, daemon=True)
        self.printer = CustomPrinter("TCPServer")
        
        self.traj=None
        
        
        self.files_extensions = {
            'txt': self.__txt_to_dataframe__,
            'xlsx': self.__xlsx_to_dataframe__,
            'mod' : self.__mod_to_dataframe__,
            'aptsource' : self.__aptsource_to_dataframe__
            # Ajoutez d'autres extensions de fichier et fonctions associées ici
        }
        
        self.technical_response_handlers = {
            "nbtraj": self.nombre_de_traj,
            "nomtraj": self.nom_de_la_traj,
            "dimtraj": self.nb_pts_trajectoire,
            "loadtraj": self.load_trajectory,
            "robt": self.send_robtargets,
            # Ajoutez d'autres motifs et fonctions associées ici
        }
        
        self.service_response_handlers = {
            "stop": self.stop,
            "closesocket" : self.close_socket,
            "closseallsockets" : self.close_all_sockets #attention : fonction non débuggé
            # Ajoutez d'autres motifs et fonctions associées ici
        }
    
        self.trajectories=self.trajectories_files()
        
    
 

    def start(self):
        """
        Démarre le serveur en liant le socket sur l'adresse et le port spécifiés.
        Accepte continuellement les connexions entrantes, créé un thread pour gérer chaque client.
        
        Returns
        -------
        None
        
        Notes
        -----
        - La méthode est appelée lorsque la commande 'start' est exécutée sur l'objet serveur.
        - Le serveur utilise un thread dédié pour vérifier le timeout des connexions.
        - Lorsqu'une nouvelle connexion est acceptée, un thread distinct est créé pour gérer ce client.
        - La méthode est conçue pour être exécutée dans une boucle infinie, mais elle peut être arrêtée en appelant la méthode 'stop'.
        - En cas d'erreur, la méthode affiche un message d'erreur et appelle la méthode 'stop'.
        """

        self.is_running = True
        
        # Démarrer le thread de vérification du timeout
        #self.timeout_thread.start()
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.printer.print_message(f"Server listening on {self.host}:{self.port}")

            while self.is_running:
                try:
                    client_socket, client_address = self.server_socket.accept()
                    if not self.is_running:
                        break  # Vérifier à nouveau après l'acceptation pour éviter une erreur après l'arrêt
                    self.printer.print_message(f"Accepted connection from {client_address}")

                    client_handler = threading.Thread(target=self.handle_client, args=(client_socket,))
                    client_handler.start()
                    self.connections.append((client_socket, client_handler))

                    # Réinitialiser le temps d'activité lorsqu'une nouvelle connexion est acceptée
                    self.last_activity_time = time.time()
                except OSError as e:
                    if self.is_running:
                        self.printer.print_error(f"Error accepting connection: {e}")

        except Exception as e:
            self.printer.print_error(f"Error starting server: {e}")
            self.stop()



    def handle_client(self, client_socket):
        """
        Gère la communication avec un client spécifique.
        
        Parameters
        ----------
        client_socket : socket.socket
            Le socket du client connecté.
        
        Returns
        -------
        None
        
        Notes
        -----
        - La méthode est appelée pour chaque client connecté.
        - Elle lit les données du client, appelle la méthode 'process_data' pour les traiter, puis envoie la réponse.
        - En cas d'erreur, elle affiche un message d'erreur.
        - La méthode continue à exécuter tant que le serveur est en cours d'exécution et que des données sont reçues du client.
        """

        try:
            while self.is_running:
                data = client_socket.recv(1024)
                
                if not data:
                    break
                
                
                # Convertir les données en une chaîne de caractères
                data_str = data.decode("utf-8")
                
                self.printer.print_message(f'Received data : {data_str}')
                
                
                # Utiliser une expression régulière pour extraire le motif et les arguments
                # ils doivent être de la forme "requete[arg1;...argn]" en str utf8
                match = re.match(r'(\w+)(?:\[(.*?)\])?', data_str)
            
            
                motif = match.group(1)
                arguments_str = match.group(2)

                
                # Si des arguments sont spécifiés, les séparer
                arguments = arguments_str.split(';') if arguments_str else None
                
                
                
                # Chercher le motif correspondant dans la table de correspondance
                if motif in self.service_response_handlers:
                    
                    # Appeler la fonction de traitement associée au motif sans arguments
                    result=self.service_response_handlers[motif](client_socket)
                
                    print(f"fonction de service effectuée {motif}")
                
                else :
                    # Traitez les données reçues selon vos besoins
                    response = self.process_data(motif,arguments)
                
                #if not self.is_running :
                if not self.is_running or client_socket.fileno() == -1:
                    break  # Vérifier à nouveau après l'acceptation pour éviter une erreur après l'arrêt
                client_socket.send(response)

                # Réinitialiser le temps d'activité après chaque envoi de données
                self.last_activity_time = time.time()
        except Exception as e:
            self.printer.print_error(f"Error handling client: {e}")
    
    
    
    
    

    def check_timeout_thread(self):
        """
        Thread pour vérifier le timeout des connexions.
        
        Notes
        -----
        - Le thread s'exécute tant que l'attribut 'is_running' est True.
        - Il appelle la méthode 'check_timeout' à intervalles réguliers.
        """


        while self.is_running:
            # Vérifier le timeout à intervalles réguliers
            time.sleep(1)
            self.check_timeout()





    def check_timeout(self):
        """
        Méthode pour vérifier si le serveur est inactif depuis un certain temps et déclencher l'arrêt en conséquence.
        
        Notes
        -----
        - Vérifie si le timeout est activé et si le temps d'inactivité a dépassé le seuil défini.
        - Si tel est le cas, affiche un message de journalisation et arrête le serveur en appelant la méthode 'stop'.
        """

        
        
        
        # Vérifier si le timeout est activé et si le temps d'inactivité a dépassé le seuil
        if self.timeout is not None and (time.time() - self.last_activity_time) > self.timeout:
            self.printer.print_message(f"Server inactive for {self.timeout} seconds. Shutting down...")
            self.stop()
    
    
    
    def close_socket(self, client_connection):
        """
        Ferme le socket du client spécifique et supprime la connexion de la liste des connexions.
    
        Parameters
        ----------
        client_connection : socket object
            Le socket du client à fermer.
            
        Returns
        -------
        None
    
        Notes
        -----
        - La méthode vérifie si 'self.connections' contient des connexions actives.
        - Elle ferme le socket spécifié et supprime sa connexion de la liste.
        - En cas d'erreur, elle affiche un message d'erreur.
        """
        # Vérifiez si des connexions sont présentes
        if self.connections:
            # Filtrez la connexion à fermer et mettez à jour la liste des connexions
            self.connections = [
                (client_socket, client_handler) 
                for client_socket, client_handler in self.connections
                if client_socket != client_connection
            ]
            
            try:
                # Fermez le socket client spécifié
                client_connection.close()
                self.printer.print_message("Socket du client spécifié fermé.")
            except Exception as e:
                self.printer.print_error(f"Erreur lors de la fermeture du socket du client spécifié : {e}")
        else:
            self.printer.print_message("Aucune connexion active à fermer.")
        
        
        


    def close_all_sockets(self,command_from_client_connection=None):
        """
        Ferme le socket du client et supprime la connexion de la liste des connexions.
        
        Returns
        -------
        None
        
        Notes
        -----
        - La méthode vérifie si 'self.connections' contient des connexions actives.
        - Pour chaque connexion, elle tente de fermer le socket et de terminer le thread associé.
        - En cas d'erreur, elle affiche un message d'erreur.
        """
        # Vérifiez si des connexions sont présentes
        if self.connections:
            for client_socket, client_handler in self.connections:
                try:
                    # Fermez le socket client
                    client_socket.send(b"stop")
                    client_socket.close()
                    self.printer.print_message("Socket du client fermé.")
                except Exception as e:
                    self.printer.print_error(f"Erreur lors de la fermeture du socket du client : {e}")
                
                
    
            # Réinitialisez la liste des connexions après la fermeture
            self.connections = []
        else:
            self.printer.print_message("Aucune connexion active à fermer.")
        
            
    
    def stop(self,command_from_client_connection=None):
        """
        Méthode pour arrêter le serveur de manière propre.
        
        Notes
        -----
        - Définit la variable 'is_running' sur False pour permettre l'arrêt du thread principal.
        - Envoie la chaîne "stop" à tous les clients connectés avant de fermer la connexion.
        - Ferme les sockets des clients et du serveur.
        """

        self.is_running=False
        
        self.printer.print_message("Arrêt du serveur")
        # Envoyer la chaîne "stop" à tous les clients connectés avant de fermer la connexion
        
        self.close_all_sockets()
        """
        for client_socket, client_handler in self.connections:
            try:
                # Envoyer la chaîne "stop"
                client_socket.send(b"stop")
                client_socket.close()
            except Exception as e:
                # Gérer les erreurs liées à l'envoi
                self.printer.print_error(f"Erreur lors de l'envoi de 'stop' au client : {e}")
            
            #try :
                # Fermer la connexion du client
                #client_socket.close()
                
            except Exception as e:
                self.printer.print_error(f"Erreur lors de la fermeture du socket client : {e}")
            
        """
        # Fermer la socket du serveur
        
        try :
            self.server_socket.close()
        except Exception as e:
            self.printer.print_error(f"Erreur lors de la fermeture du socket serveur : {e}")
            
        
    
    def __convert_to_bytes__(self,thing_to_convert, coeff_for_number=1):
        
        """
        Convertit les objects en octets
        """
        
        # Appliquer des mécanismes de traitement spécifiques pour différents types de données
        if isinstance(thing_to_convert, str):
            return thing_to_convert.encode("utf-8")
        elif isinstance(thing_to_convert, bytes):
            return thing_to_convert
        elif isinstance(thing_to_convert, int):
            number_to_convert=coeff_for_number*thing_to_convert
            return number_to_convert.to_bytes(4, byteorder='little', signed=True)
        elif isinstance(thing_to_convert, float):
            number_to_convert=coeff_for_number*thing_to_convert
            return round(number_to_convert).to_bytes(4, byteorder='little', signed=True)
        else:
            # Gérer les autres types de données ici
            return b"error"

    def process_data(self, motif,arguments):
        """
        Traite les données reçues du client.
        
        Parameters
        ----------
        data : chaine de caractère
            Données reçut du client décompilées
        
        Returns
        -------
        bytes
            La réponse à renvoyer au client, encodée en bytes.
        
        Notes
        -----
        - La méthode extrait le motif et les arguments des données, puis appelle la fonction appropriée en fonction du motif.
        - Si le motif n'est pas trouvé dans la table de correspondance, la méthode appelle la fonction 'handle_default'.
        - La méthode gère différents types de données en appliquant des mécanismes de traitement spécifiques.
        - Elle renvoie la réponse encodée en bytes.
        """
    
        
        
        try :
        
            
            # Chercher le motif correspondant dans la table de correspondance
            if motif in self.technical_response_handlers:
                
                if arguments is None :
                    # Appeler la fonction de traitement associée au motif sans arguments
                    result=self.technical_response_handlers[motif]()
                
                else :
                    # Appeler la fonction de traitement associée au motif avec l'argument
                    result=self.technical_response_handlers[motif](arguments)
                
            else:
                # Aucun motif correspondant
                result=self.handle_default(str(motif))
            
        except ValueError as e:
            # Erreur lors de l'extraction du motif et des arguments
            self.printer.print_error(f"Erreur d'extraction du motif et des arguments : {e}")
        
        coeff=1 #???
        
        bytes_to_send=self.__convert_to_bytes__(result, coeff_for_number=coeff)
        
        
        return bytes_to_send

        
        
    

    def handle_default(self,data):
        """
        Fonction de traitement par défaut pour les motifs non reconnus.
        
        Parameters
        ----------
        data : str
            Les données d'entrée non traitées.
        
        Returns
        -------
        str
            Retourne les données d'entrée sans traitement particulier avec un avertissement.
        """

        self.printer.print_warning("Fonction par défaut utilisée.")
        return data

    
    def trajectories_files(self):
        """
        Retourne la liste des fichiers présents dans le dossier 'trajectory_files' situé
        dans le répertoire du script, en filtrant les fichiers par extension.
    
        Returns
        -------
        List[str]
            Liste des noms de fichiers filtrés par extension.
        """
        # Obtient le chemin du répertoire du script
        file_path = os.path.dirname(os.path.abspath(__file__))
        dossier = str(file_path+"/trajectory_files") #ajoute le chemin du dossier
        
        try:
            # Obtenir la liste des fichiers dans le dossier
            fichiers = [f for f in os.listdir(dossier) if os.path.isfile(os.path.join(dossier, f)) and f.split('.')[-1] in self.files_extensions]
            
            return fichiers
            
        except OSError as e:
            self.printer.print_error(f"Erreur lors de la lecture du dossier {dossier}: {e}")
            return []
    
    
    
    
    def nom_de_la_traj(self,arguments):
        """
        Récupère le nom d'une trajectoire en fonction des arguments passés à la fonction.
        Si des erreurs surviennent lors de la conversion de l'argument en entier, la fonction
        affiche un message d'erreur, défini la valeur à 0 et continue avec la première trajectoire.
        Si l'entier obtenu est supérieur ou égal à la longueur de la liste de trajectoires, il est
        réinitialisé à 0, et encore une fois, la première trajectoire est retournée. Si aucun argument
        n'est fourni, un message d'erreur est affiché, et la première trajectoire est renvoyée.
        
        Parameters
        ----------
        arguments : List[str]
            Liste des arguments passés à la fonction.
        
        Returns
        -------
        str
            Le nom de la trajectoire correspondant aux arguments, ou le premier élément de la liste
            de trajectoires en cas d'erreur ou d'absence d'arguments.
        """
        
        if len(arguments)>0:
            try :
                int_arg=int(arguments[0])-1
            except Exception as e:
                int_arg=0
                self.printer.print_error(f"Argument du nom de la trajectoire non convertible en integer :{e}")
            if int_arg>=len(self.trajectories):
                int_arg=0
                self.printer.print_error("Argument passé plus grand que la longueure de la liste de fichier")
            #revoie le nom de la int_arg ième trajectoire
            return self.trajectories[int_arg]
            
        else:
            # En cas d'absence d'arguments, affiche un message d'erreur et retourne le premier élément de la liste de trajectoires
            self.printer.print_error("Aucun argument pour le nom de la trajectoire")
            return self.trajectories[0]
    
    
    def nombre_de_traj(self):
        """
        Retourne le nombre total de trajectoires disponibles.
        
        Returns
        -------
        int
            Nombre total de trajectoires disponibles.
        """
        self.trajectories=self.trajectories_files()
        to_return=len(self.trajectories)
        
        
        return to_return
    
    def nb_pts_trajectoire(self):
        """
        Retourne le nombre total de points dans la trajectoire actuellement chargée.
        
        Returns
        -------
        int
            Nombre total de points dans la trajectoire actuellement chargée.
        """

        if self.traj is None:
            self.printer.print_error("Aucune trajectoire chargée")
            return 0
        else :
            return len(self.traj)
    
    
    
    
    
    def __txt_to_dataframe__(self,dossier,wanted_columns,default_values):
        
        
        """
        FONCTION D'IMPORT
        -----------------
        Convertit un fichier texte en un DataFrame en utilisant des colonnes spécifiées et des valeurs par défaut.
        
        Parameters
        ----------
        dossier : str
            Chemin du fichier texte à convertir en DataFrame.
        wanted_columns : list[str]
            Liste des colonnes à extraire du fichier texte.
        default_values : list
            Liste des valeurs par défaut à utiliser pour chaque colonne si elles ne sont pas présentes.
        
        Returns
        -------
        None
            Cette méthode affecte le DataFrame résultant à l'attribut 'traj' de l'objet.
        """

        
        
        # Lire le fichier texte ligne par ligne
        with open(dossier, 'r') as file:
            lines = file.readlines()

        # Initialiser une liste pour stocker les données
        data = []

        # Parcourir chaque ligne du fichier
        for line in lines:
            # Convertir la chaîne de la ligne en une liste d'objets Python
            row = ast.literal_eval(line.strip()[:-1])
            
            # Étendre les listes imbriquées pour obtenir une liste à plat
            flat_row = [item for sublist in row for item in sublist]
            
            # Ajouter la ligne à la liste des données
            data.append(flat_row)

        # Créer un DataFrame avec les données et les colonnes définies
        self.traj = pd.DataFrame(data, columns=wanted_columns)
    
    
    def __xlsx_to_dataframe__(self,dossier,wanted_columns,default_values):
        
        """
        FONCTION D'IMPORT
        -----------------
        Convertit un fichier Excel en un DataFrame en utilisant des colonnes spécifiées et des valeurs par défaut.
        
        Parameters
        ----------
        dossier : str
            Chemin du fichier Excel à convertir en DataFrame.
        wanted_columns : list[str]
            Liste des colonnes à extraire du fichier Excel.
        default_values : list
            Liste des valeurs par défaut à utiliser pour chaque colonne si elles ne sont pas présentes.
        
        Returns
        -------
        None
            Cette méthode affecte le DataFrame résultant à l'attribut 'traj' de l'objet.
        """


        dataframe= pd.DataFrame(columns=wanted_columns)

        # Charger le fichier Excel dans un DataFrame
        dataframe_excel = pd.read_excel(dossier, header=0)
        dataframe_excel.columns = map(str.lower, dataframe_excel.columns)



        dataframe[['x', 'y', 'z']] = dataframe_excel[['x', 'y', 'z']]

        # Remplir les valeurs par défaut pour les colonnes manquantes
        dataframe = dataframe.fillna(value=default_values)
        
        self.traj = dataframe
        
        del(dataframe)
    
    
    def __mod_to_dataframe__(self,dossier,wanted_columns,default_values): 
        
        """
        FONCTION D'IMPORT
        -----------------
        Convertit un fichier mod en un DataFrame en utilisant des colonnes spécifiées et des valeurs par défaut.
        Il récupère toutes les structures  [[nombre, nombre, nombre], [nombre, nombre, nombre, nombre], [nombre, nombre, nombre, nombre], [nombre, nombre, nombre, nombre, nombre, nombre]] 
        
        Parameters
        ----------
        dossier : str
            Chemin du fichier mod à convertir en DataFrame.
        wanted_columns : list[str]
            Liste des colonnes à extraire du fichier.
        default_values : list
            Liste des valeurs par défaut à utiliser pour chaque colonne si elles ne sont pas présentes.
        
        Returns
        -------
        None
            Cette méthode affecte le DataFrame résultant à l'attribut 'traj' de l'objet.
        """

        data = []
        with open(dossier, 'r') as file:
            content = file.read()
            
            # Utiliser une expression régulière plus souple pour trouver toutes les occurrences de la structure spécifiée
            matches = re.findall(r'\[\[([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+)\],\s*\[([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+)\],\s*\[([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+)\],\s*\[([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+),\s*([\d.Ee+\s-]+)\]\]', content)
            for match in matches:
                # Convertir les nombres en flottants
                values = [float(val) for val in match]
                data.append(values)
                
        self.traj = pd.DataFrame(data, columns=wanted_columns)
    
    
    def __aptsource_to_dataframe__(self,dossier,wanted_columns,default_values): 
        
        """
        FONCTION D'IMPORT
        -----------------
        Convertit un fichier aptsource en un DataFrame en utilisant des colonnes spécifiées et des valeurs par défaut.
        
        ATTENTION : Il ne récupère que les coordonnées x,y,z, il ne fait pas les conversions angulaires
        
        
        Parameters
        ----------
        dossier : str
            Chemin du fichier aptsource à convertir en DataFrame.
        wanted_columns : list[str]
            Liste des colonnes à extraire du fichier.
        default_values : list
            Liste des valeurs par défaut à utiliser pour chaque colonne si elles ne sont pas présentes.
        
        Returns
        -------
        None
            Cette méthode affecte le DataFrame résultant à l'attribut 'traj' de l'objet.
        """
        
        data = []
        with open(dossier, 'r') as file:
            
            
            for ligne in file:
                # Vérifier si la ligne contient le motif "GOTO"
                if "GOTO" in ligne:
                    # Extraire les nombres après le motif "/"
                    valeurs = [float(x.strip()) for x in ligne.split('/')[1].split(',')]
                    
                    # Ajouter les valeurs à la liste des données
                    data.append(valeurs)
            
        
        
        # Créer un DataFrame à partir de la liste des données
        dataframe_aptsource = pd.DataFrame(data, columns=['x', 'y', 'z', 'projx', 'projy', 'projz'])
        
        #print(dataframe_aptsource)
        
        #créer le dataframe souhaité
        dataframe= pd.DataFrame(columns=wanted_columns)


        dataframe[['x', 'y', 'z']] = dataframe_aptsource[['x', 'y', 'z']]
        
        #print(dataframe)
        # Remplir les valeurs par défaut pour les colonnes manquantes
        dataframe = dataframe.fillna(value=default_values)
        
        #print(dataframe)
        
        self.traj = dataframe
        
        del(dataframe_aptsource)
        del(dataframe)
            
          
        
        
    
    
    
    
    
        
    def load_trajectory(self,arguments):
        """
        Charge une trajectoire en fonction des arguments fournis, convertit le fichier en DataFrame
        et stocke le DataFrame résultant dans l'attribut 'traj'. Cette fonction fait appel aux sous 
        fonctions spécialisées pour chaque type de fichier.
        
        Parameters
        ----------
        arguments : list[str]
            Liste des arguments passés pour spécifier la trajectoire. Si aucun argument n'est fourni,
            charge la première trajectoire de la liste par défaut.
        
        Returns
        -------
        str
            Un message indiquant si le chargement a réussi ('loaded') ou s'il y a eu une erreur ('error').
            Cette méthode utilise les fonctions spécifiées pour traiter différents types de fichiers
            en fonction de leur extension.
        """

        
        
        if len(arguments)>0:
            try :
                int_arg=int(arguments[0])-1
            except Exception as e:
                int_arg=0
                self.printer.print_error(f"Argument du nom de la trajectoire non convertible en integer :{e}")
            if int_arg>=len(self.trajectories):
                int_arg=0
                self.printer.print_error("Argument passé plus grand que la longueure de la liste de fichier")
        else:
             self.printer.print_error("Aucun argument pour le nom de la trajectoire")
             int_arg=0
             
        
        file_path = os.path.dirname(os.path.abspath(__file__))
        dossier = str(file_path+"/trajectory_files/"+self.trajectories[int_arg])
        extension = dossier.split('.')[-1]
        
        self.printer.print_message(f"Try to load {self.trajectories[int_arg]}")
        
        # Définir le nom de vos colonnes
        wanted_columns = ['x', 'y', 'z', 'q1', 'q2', 'q3', 'q4', 'cf1', 'cf4', 'cf6', 'cfx', 'eax_a', 'eax_b', 'eax_c', 'eax_d', 'eax_e', 'eax_f']
        # Définir les valeurs par défaut pour les colonnes manquantes
        default_values = {
            'q1': 0,
            'q2': 0,
            'q3': 1,
            'q4': 0,
            'cf1': 0,
            'cf4': 0,
            'cf6': 0,
            'cfx': 0,
            'eax_a': 9E+09,
            'eax_b': 9E+09,
            'eax_c': 9E+09,
            'eax_d': 9E+09,
            'eax_e': 9E+09,
            'eax_f': 9E+09  }
                
        
        if extension in self.files_extensions:
            fonction_traitement = self.files_extensions[extension]
            fonction_traitement(dossier,wanted_columns,default_values)
            
            return "loaded"
        else:
            self.printer.print_error(f"Aucune fonction de traitement n'est définie pour l'extension {extension}.")
            return 'error'
        
        
        
        
    def send_robtargets(self,arguments):
        
        """
        Envoie les coordonnées des robtargets sous forme de bytes après avoir appliqué des
        coefficients multiplicatifs aux différentes colonnes du DataFrame de la trajectoire.
        
        Parameters
        ----------
        arguments : list[str]
            Liste des arguments permettant de spécifier la référence de ligne et le nombre de robtargets
            à envoyer. Si aucun argument n'est fourni, envoie par défaut la première ligne.
        
        Returns
        -------
        bytes
            Les données des robtargets encodées en bytes prêtes à être envoyées au client.
        
        Notes
        -----
        - Si aucun argument n'est passé, envoie par défaut la première ligne de la trajectoire.
        - Les coefficients multiplicatifs sont appliqués pour mettre les valeurs des colonnes à l'échelle désirée.
        - Les valeurs sont arrondies et encodées en bytes avec gestion du dépassement de capacité.
        """

        
        
        if self.traj is None:
            self.printer.print_error("robt : Aucune trajectoire passée")
            return 'error'
        
        
        
        
        
        if arguments is None or len(arguments)==0:
            
            self.printer.print_error("robt : Aucun argument passé")
            return 'error'
        
        if not self.nb_pts_trajectoire() >0:
            self.printer.print_error("robt : Aucun point dans la trajectoire")
            return 'error'
        
        elif  len(arguments)==1:
            self.printer.print_warning("robt : Un seul argument passé, par défaut la ligne de référence est la première ligne")
            ref_ligne=int(arguments[0])
            number_target=1
        elif len(arguments)>1:
            try :
                ref_ligne=int(arguments[0])-1
                number_target=int(arguments[1])
                if ref_ligne<0:
                    self.printer.print_error("robt : ligne de référence négative (bouclage par la fin)")
                if number_target<=0:
                    self.printer.print_error("robt : nombre de robtarget demandé négatif ou nul, par défaut : 1")
                    number_target=1
                    
                if ref_ligne>=len(self.traj):
                    self.printer.print_warning("robt : ligne de référence en dehors de la plage de la trajectoire : bouclage de la référence ")
                    ref_ligne=ref_ligne % len(self.traj)
                if ref_ligne+number_target > len(self.traj):
                    self.printer.print_warning("robt : nombre de robtarget demandé engendre un dépassement de la longueur de la trajectoire")
                    number_target=len(self.traj)-ref_ligne
                    
            except Exception as e:
                ref_ligne=0
                number_target=1
                
                self.printer.print_error(f"robt : Argument du nom de la trajectoire non convertible en integer :{e}")
        
        
        multiplication_factor = {
            'x' : 1000,
            'y' : 1000,
            'z' : 1000,
            'q1': 1000000,
            'q2': 1000000,
            'q3': 1000000,
            'q4': 1000000,
            'cf1': 1,
            'cf4': 1,
            'cf6': 1,
            'cfx': 1,
            'eax_a': 1000,
            'eax_b': 1000,
            'eax_c': 1000,
            'eax_d': 1000,
            'eax_e': 1000,
            'eax_f': 1000  }
        
        
        dataframe_to_send=self.traj.iloc[ref_ligne:ref_ligne+number_target]
        dataframe_to_send=dataframe_to_send.mul(multiplication_factor)
        points_to_send = np.array(dataframe_to_send).reshape(-1)
        
        self.printer.print_message("des points ont été envoyés")
        #self.printer.print_message(f"points envoyés : {dataframe_to_send}")
        #self.printer.print_message(f"points envoyés : {points_to_send}")
        #print("points_to_send : ",points_to_send)
        
        nb_bytes = 4
        is_signed = True
        bytes_concatenes = b"".join(min(round(f),(2**(8*nb_bytes-int(is_signed)))-1).to_bytes(nb_bytes, byteorder='little', signed=is_signed) for f in points_to_send)
        """
        fonctionne aussi :
        bytes_concatenes = b"".join(struct.pack('>i', round(f)) for f in points_to_send)
        """
        
        return bytes_concatenes
        
        
        
        
    
    
    

    





"""
##########################################################################

Déclaration de fonctions

##########################################################################
"""





def main_server(input_adress_ip,input_port,input_time_out,*args):
    
    """
     Fonction principale pour lancer un serveur avec des options personnalisables.
    
     Args:
         *args: Fonctions optionnelles à exécuter lorsque le serveur est actif.
    
     Exemple d'utilisation:
         main_server(
             fonction1,
             fonction2,
             ...
         )
    
     Si des fonctions sont spécifiées en arguments, elles seront exécutées une fois que le
     serveur sera actif. Sinon, la fonction entre dans une boucle infinie, maintenant le
     serveur actif jusqu'à ce qu'une interruption clavier (Ctrl+C) soit détectée.
    
     Paramètres:
         host (str): Adresse IP du serveur.
         port (int): Numéro de port du serveur.
         timeout (float): Délai d'attente en secondes pour les connexions (non utilisé dans l'exemple).
    
     Raises:
         KeyboardInterrupt: Arrête le serveur en cas d'interruption clavier (Ctrl+C).
     """
    
    
    
    try:
                
        
        host=input_adress_ip
        
        
        port = 50000
        port=input_port
        timeout = input_time_out

        if IsIPAddress(host):
            server = TCPServer(host, port, timeout=timeout, printer=CustomPrinter("Main"))
            server_thread = threading.Thread(target=server.start, daemon=True)
            server_thread.start()

            
            # Attendre que le serveur soit actif (pour être sur)
            time.sleep(1)
            
            
            
            
            if len(args) > 0:
                # Si des arguments sont passés, exécute les fonctions
                for func in args:
                    print(f"Tentative d'exécution de : {func} \n")
                    try:
                        func()
                        
                        print(f"Fin de la fonction de : {func}")
                    except Exception as e:
                        print(f"Erreur lors de l'exécution de la fonction : {e}")
                        
                        
            else:
                while server.is_running:
                    time.sleep(0.001)
            
            
            
        else:
            print("Invalid IP address")

    except KeyboardInterrupt:
        print("Server shutting down due to keyboard interuption...")
        server.stop()
    
    
    finally:
        #time.sleep(1) #???
        
        if server.is_running:
            
            
            server.stop()
        print("fin programme")




# fonction de test 


def client_example():
    
    """
    Exemple d'un client TCP qui se connecte à un serveur et envoie/reçoit des données.
    
    Sert à tester le code
    
    Le client se connecte à un serveur à l'adresse spécifiée et au port donné. Il envoie
    plusieurs messages au serveur et affiche les réponses reçues.

    
    Raises:
        Exception: Capture toute exception survenue lors de la communication avec le serveur.
    """
    
    
    time.sleep(1)
    
    #host = "10.118.155.5"
    host = "127.110.118.82"
    port = 50000

    printer_client=CustomPrinter("TCP_client")


    # Créer un socket TCP
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Se connecter au serveur
        client_socket.connect((host, port))
        printer_client.print_message(f"Connected to {host}:{port} ")
        
        
        
        # Envoyer des données au serveur
        message = b"nbtraj"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        data = client_socket.recv(1024)
        
        unpacked_data=struct.unpack('<i', data)[0]

        
        printer_client.print_message(f"Received from server: { unpacked_data }")
        
        
        
        
        # Envoyer des données au serveur
        message = b"nomtraj[1]"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        data = client_socket.recv(1024)
        
        
        printer_client.print_message(f"Received from server: { data.decode('utf-8') }")
        
         
        
        
        
        # Envoyer des données au serveur
        message = b"loadtraj[1]"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        data = client_socket.recv(1024)
        
        printer_client.print_message(f"Received from server: { data.decode('utf-8')}")
        
        
        
        
        
        
        
        
        # Envoyer des données au serveur
        message = b"dimtraj"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        data = client_socket.recv(1024)
        
        printer_client.print_message(f"Received from server: { struct.unpack('>i', data) }")
        
        
        
        
        
        # Envoyer des données au serveur
        message = b"robt[3;5]"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        bytes_paquet  = client_socket.recv(1024)
        
        # Nombre d'entiers dans le paquet
        n_entiers = len(bytes_paquet) // 4
        
        
        """
        #old code
        # Décoder les bytes en entiers (int32)
        entiers_decodes = np.frombuffer(bytes_paquet, dtype=np.int32)
        
        # Organiser les entiers dans une matrice de 17 colonnes et n lignes
        matrice = entiers_decodes.reshape((n_entiers // 17, 17))
        """
        
        floats_decodes = [struct.unpack('<i', bytes_paquet[i:i+4])[0] for i in range(0, len(bytes_paquet), 4)]

        # Organiser les floats dans une matrice de 17 colonnes et n lignes
        matrice = np.array(floats_decodes).reshape((n_entiers // 17, 17))
        
        time.sleep(1)
        
        print("Matrice résultante:")
        print(matrice)
        
        #printer_client.print_message(f"Received from server: { data.decode('utf-8')}")
        
        
        
        
        
        
        
        
        # Fermeture du soccet
        
        message = b"closesocket"
        client_socket.sendall(message)
        
        
       
        
        
        
        
        

        """
        # Envoyer des données au serveur
        message = b"stop"
        client_socket.sendall(message)
        
        # Recevoir la réponse du serveur
        data = client_socket.recv(1024)
        
        
        printer_client.print_message(f"Received from server: { data.decode('utf-8') }")
        
        """
        
        
        
        
        
        
    

    except Exception as e:
        printer_client.print_error(f"Erreur lors de la communication avec le serveur: {e}")

    finally:
        
        # Fermer la connexion
        
        time.sleep(0.5) #???
        
        print("fin client")
        
        







"""
##########################################################################

Code principal

##########################################################################
"""


def main():

    print("""                 
                          $$$$$$$$$                 $                            
                           $$$$$$$$$               $$$                            
                            $$$$$$$$$             $$$$$                           
                             $$$$$$$$$           $$$$$$$                          
                              $$$$$$$$$         $$$$$$$$$                         
                               $$$$$$$$$         $$$$$$$$$                        
                                $$$$$$$$$         $$$$$$$$$                       
                                 $$$$$$$$$         $$$$$$$$$                      
                                  $$$$$$$$$         $$$$$$$$$                     
                      ;;;;;;;;     $$$$$$$$$         $$$$$$$$$                    
                     ;;;;;;;;.      $$$$$$$$$         $$$$$$$$$                   
                    ;;;;;;;;:        $$$$$$$$$         $$$$$$$$$                  
                   ;;;;;;;;;          $$$$$$$$$         $$$$$$$$$                 
                  ;;;;;;;;;            $$$$$$$$$         $$$$$$$$$                                                                                                           
_______________________________________________________________________________

       _____   ___     _     __   __   ___   _  __ _____   ___   ___
      /_  _/  / o |  .' \   / / ,'_/  / _/  / |/ //_  _/  / _/  / o |
       / /   /  ,'  / o /n_/ / / /_  / _/  / || /  / /   / _/  /  ,'
      /_/   /_/`_\ /_n_/ \_,'  |__/ /___/ /_/|_/  /_/   /___/ /_/`_\

_______________________________________________________________________________
                                                                                 
             $$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$    $            
            $$$$XXX$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$    $$$            
         ;;$$$+   $$$$$$$.         $.         $;         $$$$    + $+            
        ;;$$$+   $$$$$$.   x$$$   ..   $$$$$$+   ;$$$   $$$$    +  | +           
       ;;$$$+   $$$$$$    $$$$$$$$.        $    $$$$$$$$$$$    +   |  +          
      ;;$$$+   $$$$$$    $$$$$$$$.   :::::$    $$$$$$$$$$$    +    |   +        
     ;;$$$+   $$$$$$+   .$$$    .   $$$$$$$    $$$    $$$    +   $$$$   +       
    ;;$$$+         $$        .$.   $$$$$$$$         $$$$    +  .$XX&XX$. +     
   ;;$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$    +  ..$$&&$$..  +     
  ;;$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$   $$  /   $&&$   \  $$   
 ;;;;;;;;;;;;;;;;;;;;;;;:;;;;;;;;:;;;;;;;;;;;;;;;;;    $$$$$/            \$$$$$ 
;;;;;:;;;;:.;;;;;;;;:;;;;::;;;;;;;::;;;:;;;:;:;;;;     $$$$++++++++++++++++$$$ 
                                                         $                   $  
  
         
          
          
    @Date : 28/02/2024

    @Author: 2019-0248 : Clément RACINET (pour la partie python uniquement)

    Projet TRAJCENTER
    J.SCHUMACKER & C.RACINET


    Description : 
        Le but de ce code est d'envoyer au robot sur requête TCP/IP les points 
        Le code python est serveur et le robot client.
 
        
    """)
    
    while True:
        try:
            input_IP_adress = input("Entrez l'adresse IP du serveur : ")
            if IsIPAddress(str(input_IP_adress)):
                break

        except ValueError:
            print("Erreur : Veuillez saisir une adresse IP.")

       
    while True:
       try:
           input_port = input("Entrez le port de communication avec le serveur : ")
           input_port=round(float(input_port))
           break
       except ValueError:
           print("Erreur : Veuillez saisir un entier.")
           
           
    while True:
       try:
           input_timeout = input("Entrez la valeur du timeout [s] (entrer inf si pas de timeout): ")
           
           if input_timeout=='inf':
               input_timeout=np.inf
               break
           else:
               input_timeout=round(float(input_timeout))
               break
               
       except ValueError:
           print("Erreur : Veuillez saisir un entier.")
    
    
    print("\n")
    print(f"Adresse IP : {input_IP_adress}")
    print(f"Port : {input_port}")
    print(f"Time Out : {input_timeout} s")
    
    main_server(input_IP_adress,input_port,input_timeout)
    
    



"""
main()

"""


print("Test avec mon code perso")
main_server("127.110.118.82",50000,np.inf,client_example)


"""
print("\n\n\n")
print("----------------------------------------------------------")
print("\n\n\n")

print("Démarage du serveur en infini")
main_server()
"""



