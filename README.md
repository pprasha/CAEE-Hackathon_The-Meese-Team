\documentclass[11pt, a4paper]{article}

% --- UNIVERSAL PREAMBLE BLOCK ---
\usepackage[a4paper, top=2.5cm, bottom=2.5cm, left=2cm, right=2cm]{geometry}
\usepackage{fontspec}

\usepackage[english, bidi=basic, provide=*]{babel}

\babelprovide[import, onchar=ids fonts]{english}

% Set default/Latin font to Sans Serif in the main (rm) slot
\babelfont{rm}{Noto Sans}
% Set monospaced font for code
\babelfont{mono}{Noto Sans Mono}

% --- END UNIVERSAL BLOCK ---

% Load packages for styling
\usepackage[svgnames]{xcolor}
\usepackage{enumitem}     % For customizing lists
\usepackage{listings}     % For code blocks
\usepackage{titling}      % To customize title
\usepackage{hyperref}     % For clickable links (must be loaded late)

% --- Style Definitions ---

% Define colors for code blocks (GitHub-like light gray)
\definecolor{codebg}{gray}{0.95}
\definecolor{codeframe}{gray}{0.88}
\definecolor{linkblue}{RGB}{9, 105, 218}

% Configure list spacing to be tighter
\setlist{nosep, itemsep=3pt}

% Configure code blocks (listings)
\lstdefinestyle{githubstyle}{
    backgroundcolor=\color{codebg},    % Light gray background
    basicstyle=\small\ttfamily,       % Use small monospaced font
    breaklines=true,                  % Break long lines
    frame=single,                     % Single frame border
    frameround=tttt,                  % Rounded corners (top-left, top-right, bottom-left, bottom-right)
    rulecolor=\color{codeframe},      % Border color
    framexleftmargin=6pt,             % Padding
    framexrightmargin=6pt,
    framextopmargin=6pt,
    framexbottommargin=6pt,
    language=bash,                    % Default language
    keywordstyle=\color{blue},
    stringstyle=\color{red},
    commentstyle=\color{ForestGreen},
}
\lstset{style=githubstyle} % Apply this style globally

% Configure links
\hypersetup{
    colorlinks=true,
    linkcolor=linkblue,
    urlcolor=linkblue,
    citecolor=linkblue,
    filecolor=linkblue,
    breaklinks=true,
    pdfborder={0 0 0} % No box around links
}

% --- Title Customization ---
\pretitle{\begin{flushleft}\Huge\bfseries}
\posttitle{\end{flushleft}\vspace{0.5em}}
\preauthor{\begin{flushleft}\large}
\postauthor{\end{flushleft}\vspace{1em}}
\predate{}
\postdate{}

\title{AirStack Space Optimizer}
\author{
    \textbf{Hackathon Project} | A logistics tool for optimizing emergency cargo transport in remote areas.
    \vspace{1em} \\
    \textbf{Live Demo:} \href{https://caee-hackathon-the-moose-team.onrender.com/}{\nolinkurl{caee-hackathon-the-moose-team.onrender.com}}
}
\date{} % No date

% Remove page numbering
\pagestyle{empty}

% --- Document Body ---
\begin{document}

\maketitle

% Use unnumbered sections, like a README
\section*{1. The Problem}

In disaster scenarios, remote and rural communities (like those in Alaska) are critically dependent on helicopter transport for emergency supplies. This vital supply chain is plagued with inefficiencies:

\begin{itemize}
    \item \textbf{Wasted Space:} Globally, 30-50\% of cargo volume is wasted due to inefficient packing.
    \item \textbf{Critical Delays:} Inefficiencies contribute to 24-48 hour delays in delivering aid.
    \item \textbf{High Costs:} Wasted fuel from poorly optimized loads directly translates to wasted money and resources.
    \item \textbf{Logistical Hurdles:} Ground crews lack the tools to quickly and safely load aircraft based on dynamic supply requests.
\end{itemize}

\section*{2. Our Solution: AirStack}

\textbf{AirStack} is a web-based logistics tool designed to solve this problem. It provides a simple interface for administrators to manage cargo requests and a powerful backend to generate optimized loading plans for helicopter crews.

Our solution focuses on maximizing cargo capacity for a \textbf{UH-60 Black Hawk} helicopter, ensuring that every flight delivers the maximum possible aid, saving time, money, and ultimately, lives.

\section*{3. Key Features}

\subsection*{Admin View:}
\begin{itemize}
    \item \textbf{Submit Cargo Requests:} An administrator can add items to a pending list, selecting from preset cargo types (e.g., water, food, first-aid) and assigning a priority level (1-10).
    \item \textbf{Aircraft Configuration:} Pre-filled with the specs for a UH-60 Black Hawk (max weight, length, width, height).
    \item \textbf{Generate Layout:} With a single click, our optimization algorithm processes all pending requests.
    \item \textbf{Optimization Dashboard:} Instantly view the results of the layout, including:
    \begin{itemize}
        \item \textbf{Weight Utilization:} See exactly what percentage of the aircraft's weight capacity is used.
        \item \textbf{Items Packed/Unpacked:} Get a clear count of what fit and what's left for the next flight.
        \item \textbf{Weight Balance:} View a balance score and front/rear weight distribution to ensure aircraft safety.
    \end{itemize}
\end{itemize}

\subsection*{Loading Crew View:}
\begin{itemize}
    \item \textbf{Real-time Plan:} Ground crews can access a "Loading Crew View" to see the most recently generated loading plan.
    \item \textbf{Refresh On-Demand:} A refresh button ensures they always have the latest instructions.
\end{itemize}

\subsection*{Exportable Loading Plans:}
\begin{itemize}
    \item \textbf{2D PDF Slices:} Generate a printable PDF that breaks the cargo bay into four vertical slices, showing the ground crew \textit{exactly} where to place each item.
    \item \textbf{3D OpenSCAD Model:} Export a \texttt{.scad} file to view a complete 3D model of the optimized load.
\end{itemize}

\section*{4. How It Works}

The backend is a Flask application that runs a sophisticated optimization algorithm.

\begin{enumerate}
    \item \textbf{Prioritization:} The algorithm first sorts all pending cargo requests, prioritizing high-priority items first, then by weight.
    \item \textbf{Weight Balancing:} It intelligently places items to distribute weight evenly across four quadrants of the cargo bay (front-left, front-right, rear-left, rear-right), which is critical for helicopter flight stability.
    \item \textbf{Packing \& Validation:} The algorithm places items one by one, checking against the Black Hawk's physical dimensions (length, width, height) and max weight.
    \item \textbf{Reporting:} Once complete, it provides a full report on what was packed, what was left, and the final center of gravity.
\end{enumerate}

\section*{5. Technology Stack}

\begin{itemize}
    \item \textbf{Backend:} \href{https://flask.palletsprojects.com/}{Flask}
    \item \textbf{Frontend:} HTML, JavaScript, and \href{https://tailwindcss.com/}{Tailwind CSS}
    \item \textbf{PDF Generation:} \href{https://www.reportlab.com/}{ReportLab}
    \item \textbf{3D Model Generation:} \href{https://openscad.org/}{OpenSCAD} (via text file generation)
    \item \textbf{Deployment:} \href{https://gunicorn.org/}{Gunicorn} (on \href{https://render.com/}{Render})
\end{itemize}

\section*{6. Future Plans}

\begin{itemize}
    \item \textbf{Full Deployment:} Deploy at the Bethel Operations Center in Alaska.
    \item \textbf{Partnerships:} Contract with Alaska Homeland Security, Tribal Emergency Response Orgs, and the Alaska National Guard.
    \item \textbf{Secure Infrastructure:} Set up a permanent, secure server with dedicated admin and crew logins.
\end{itemize}

\section*{7. How to Run Locally}

\begin{enumerate}
    \item \textbf{Clone the repository:}
\begin{lstlisting}
git clone https://github.com/your-username/airstack.git
cd airstack
\end{lstlisting}

    \item \textbf{Create and activate a virtual environment:}
\begin{lstlisting}
# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
.\venv\Scripts\activate
\end{lstlisting}

    \item \textbf{Install dependencies:}
\begin{lstlisting}
pip install -r requirements.txt
\end{lstlisting}

    \item \textbf{Run the application:}
\begin{lstlisting}
# Using Gunicorn (for production-like environment)
gunicorn app:app

# Or using Flask's built-in server (for development)
flask run
\end{lstlisting}

    \item Open your browser and navigate to \href{http://127.0.0.1:5000}{\nolinkurl{http://127.0.0.1:5000}} (or \href{http://127.0.0.1:8000}{\nolinkurl{http://127.0.0.1:8000}} if using gunicorn).
\end{enumerate}

\end{document}
