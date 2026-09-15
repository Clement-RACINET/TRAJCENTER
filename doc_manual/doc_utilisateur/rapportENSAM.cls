\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{rapportENSAM}[2026/09/15 Classe de rapport technique et industriel ENSAM]

\LoadClass[a4paper,12pt]{article}

%-----------------------------------------------------------------------
% 1. Encodage & Typographie
%-----------------------------------------------------------------------
\RequirePackage[utf8]{inputenc}
\RequirePackage[T1]{fontenc}
\RequirePackage[french]{babel}
\RequirePackage{lmodern}

%-----------------------------------------------------------------------
% 2. Géométrie & En-têtes (headheight dimensionné à 35pt pour le logo)
%-----------------------------------------------------------------------
\RequirePackage[left=2cm,right=2cm,top=2.5cm,bottom=2.5cm,headheight=35pt]{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{lastpage}
\RequirePackage{wallpaper}
\RequirePackage[section]{placeins}
\RequirePackage{wrapfig}
\RequirePackage{lipsum}

%-----------------------------------------------------------------------
% 3. Mathématiques & Sciences
%-----------------------------------------------------------------------
\RequirePackage{mathtools}
\RequirePackage{amssymb}
\RequirePackage{siunitx}
\sisetup{locale = FR, detect-all}

%-----------------------------------------------------------------------
% 4. Graphiques & Figures
%-----------------------------------------------------------------------
\RequirePackage{graphicx}
\RequirePackage{float}
\RequirePackage[justification=centering]{caption}
\RequirePackage{subcaption}
\RequirePackage{tikz}
\usetikzlibrary{babel}
\RequirePackage[european]{circuitikz}
\RequirePackage{tkz-tab}

%-----------------------------------------------------------------------
% 5. Tableaux & Encadrés
%-----------------------------------------------------------------------
\RequirePackage{tabularx}
\RequirePackage{multirow}
\RequirePackage{colortbl}
\RequirePackage{fancybox}
\RequirePackage{thmbox}
\RequirePackage{soul}

%-----------------------------------------------------------------------
% 6. Couleurs & Listings
%-----------------------------------------------------------------------
\RequirePackage[x11names,table]{xcolor}

\definecolor{codegreen}{rgb}{0,0.6,0}
\definecolor{codegray}{rgb}{0.5,0.5,0.5}
\definecolor{codepurple}{rgb}{0.58,0,0.82}
\definecolor{backcolour}{rgb}{0.96,0.96,0.94}
\definecolor{orangeAM}{RGB}{255, 163, 0}
\definecolor{violetAM}{RGB}{128, 39, 108}

\RequirePackage{listings}
\lstdefinestyle{mystyle}{
    backgroundcolor=\color{backcolour},   
    commentstyle=\color{codegreen},
    keywordstyle=\color{magenta},
    numberstyle=\tiny\color{codegray},
    stringstyle=\color{codepurple},
    basicstyle=\ttfamily\footnotesize,
    breakatwhitespace=false,         
    breaklines=true,                 
    captionpos=b,                    
    keepspaces=true,                 
    numbers=left,                    
    numbersep=5pt,                  
    showspaces=false,                
    showstringspaces=false,
    showtabs=false,                  
    tabsize=2
}
\lstset{style=mystyle}

%-----------------------------------------------------------------------
% 7. Sommaire et Numérotation
%-----------------------------------------------------------------------
\RequirePackage{tocbasic}
\RequirePackage{sectsty}

\sectionfont{\color{orangeAM}}
\subsectionfont{\color{violetAM}}

\numberwithin{figure}{section}
\numberwithin{table}{section}
\numberwithin{equation}{section}

%-----------------------------------------------------------------------
% 8. Hyperliens sans cadres
%-----------------------------------------------------------------------
\RequirePackage{url}
\RequirePackage[
    hidelinks,
    pdfhighlight=/I,
    pdfencoding=auto,
    psdextra
]{hyperref}

%-----------------------------------------------------------------------
% 9. Métadonnées du document
%-----------------------------------------------------------------------
\newcommand{\@logoInstitution}{logos/logo-arts-et-metiers.jpg}
\newcommand{\logoInstitution}[1]{\renewcommand{\@logoInstitution}{#1}}

\newcommand{\@fondPageGarde}{logos/fond.PNG}
\newcommand{\fondPageGarde}[1]{\renewcommand{\@fondPageGarde}{#1}}

\newcommand{\@organisme}{École Nationale Supérieure d'Arts et Métiers}
\newcommand{\organisme}[1]{\renewcommand{\@organisme}{#1}}
\newcommand{\ecole}[1]{\organisme{#1}}

\newcommand{\@monTitre}{}
\newcommand{\titre}[1]{\renewcommand{\@monTitre}{#1}\title{#1}}

\newcommand{\@contexte}{}
\newcommand{\contexte}[1]{\renewcommand{\@contexte}{#1}}
\newcommand{\UE}[1]{\contexte{#1}}

\newcommand{\@sujet}{}
\newcommand{\sujet}[1]{\renewcommand{\@sujet}{#1}}

\newcommand{\@auteur}{}
\newcommand{\auteur}[1]{\renewcommand{\@auteur}{#1}}
\newcommand{\eleve}[1]{\auteur{#1}}

\newcommand{\@labelAuteur}{Auteurs :}
\newcommand{\labelAuteur}[1]{\renewcommand{\@labelAuteur}{#1}}

\newcommand{\@labelSuperviseur}{Encadrement :}
\newcommand{\labelSuperviseur}[1]{\renewcommand{\@labelSuperviseur}{#1}}
\newcommand{\@superviseur}{}
\newcommand{\superviseur}[1]{\renewcommand{\@superviseur}{#1}}
\newcommand{\enseignant}[1]{\superviseur{#1}}
\newcommand{\tuteur}[1]{\superviseur{#1}}

\newcommand{\espace}{\vspace{0.2cm}}

%-----------------------------------------------------------------------
% 10. En-têtes et Pieds de page
%-----------------------------------------------------------------------
\newcommand{\fairemargesintro}{
    \pagestyle{fancy}
    \fancyhf{}
    \fancyheadoffset{0cm}
    \setlength{\headheight}{35pt}
    \lhead{\IfFileExists{\@logoInstitution}{\includegraphics[height=1cm]{\@logoInstitution}}{}}
    \rhead{\today}
    \cfoot{\thepage}
}

\newcommand{\fairemarges}{
    \pagestyle{fancy}
    \fancyhf{}
    \fancyheadoffset{0cm}
    \setlength{\headheight}{35pt}
    \lhead{\IfFileExists{\@logoInstitution}{\includegraphics[height=1cm]{\@logoInstitution}}{}}
    \rhead{\today}
    \rfoot{Page \thepage/\pageref{LastPage}}
}

%-----------------------------------------------------------------------
% 11. Page de Garde (auteurs remontés au-dessus de la bande inférieure)
%-----------------------------------------------------------------------
\newcommand{\fairepagedegarde}{
\begin{titlepage}
    \IfFileExists{\@fondPageGarde}{\ThisLRCornerWallPaper{1}{\@fondPageGarde}}{}
    
    \centering
    \IfFileExists{\@logoInstitution}{
        \includegraphics[width=0.45\textwidth]{\@logoInstitution}\par
    }{}
    \vspace{0.8cm}
    
    {\scshape\Large \@organisme \par}
    
    \vspace{1.5cm}
    \rule{\linewidth}{0.3mm} \\[0.4cm]
    {\huge\bfseries \@monTitre \par}
    \rule{\linewidth}{0.3mm} \\[0.8cm]
    
    \ifx\@contexte\@empty\else
        {\scshape\large \@contexte \par}
        \vspace{0.4cm}
    \fi
    
    \ifx\@sujet\@empty\else
        {\large \textit{\@sujet} \par}
        \vspace{0.6cm}
    \fi
    
    \vspace{1cm}
    
    % Bloc des auteurs remonté (hauteur fixe et au-dessus de la frise de fond)
    \begin{minipage}{0.9\textwidth}
        \begin{minipage}[t]{0.48\textwidth}
            \begin{flushleft}
                \textbf{\@labelAuteur}\\[0.2cm]
                \@auteur
            \end{flushleft}
        \end{minipage}
        \hfill
        \begin{minipage}[t]{0.48\textwidth}
            \begin{flushright}
                \ifx\@superviseur\@empty
                \else
                    \textbf{\@labelSuperviseur}\\[0.2cm]
                    \@superviseur
                \fi
            \end{flushright}
        \end{minipage}
    \end{minipage}
    
    \vspace{1cm}
    {\large \today \par}
    
    \vfill
    \vspace{2.5cm} % Marge de sécurité pour ne pas marcher sur le bandeau bas
\end{titlepage}
}

\newcommand{\insererfigure}[4][0.7\textwidth]{
    \begin{figure}[H]
        \centering
        \includegraphics[width=#1]{#2}
        \caption{#3}
        \label{fig:#4}
    \end{figure}
}
