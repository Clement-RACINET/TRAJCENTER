#!/usr/bin/env python3
"""ASCII and Unicode logos for the TrajCenter TUI."""

from __future__ import annotations

from rich.text import Text

AM_VIOLET = r"""
                                                            
                                                            
              llllllllll                ll                  
               llllllllll              llll                 
                llllllllll            llllll                
                 llllllllll          llllllll               
                  llllllllll        llllllllll              
                   llllllllll        llllllllll             
                    llllllllll        llllllllll            
                     llllllllll        llllllllll           
                      llllllllll        llllllllll          
                       llllllllll        llllllllll         
                        llllllllll        llllllllll        
                         llllllllll        llllllllll       
                          llllllllll        llllllllll      
                                                            

                                                            
                                                            
"""


AM_ORANGE = r"""
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
                                                            
        kkkkkkkkkk                                          
       kkkkkkkkkk                                           
      kkkkkkkkkk                                            
     kkkkkkkkkk                                             
                                                            
                                                            
                                                            
"""


LCFC_ORANGE = r"""

                    oooo                  
                  oooooooo                
                 oooooooooo               
                  oooooooo                
                    oooo                  
                   //||\\                 
                  // || \\                
                 //  ||  \\               
                //   ||   \\              
               //          \\             
              //            \\            
             //              \\           
          oooo     //   \\     oooo       
        oooooooo //       \\ oooooooo     
       oooooooooo___________oooooooooo    
        oooooooo=============oooooooo     
          oooo                 oooo       
"""


LCFC_VIOLET = r"""
                                            
                                            
                                            
                                            
                                            
                                            
                                            
                                            
                    oooo                  
                  oooooooo                
                 oooooooooo               
                  oooooooo                
                    oooo                  
                                            
                                            
                                            
                                            
"""


AM_TEXT_1 = "Arts et Métiers"
AM_TEXT_2 = "Sciences et Technologies"

LCFC_TEXT_1 = "LCFC"
LCFC_TEXT_2 = "Laboratoire de Conception Fabrication Commande"


TRAJCENTER_ASCII = r"""
  _______   _____                    _    _____   ______   _   _   _______   ______   _____  
 |__   __| |  __ \       /\         | |  / ____| |  ____| | \ | | |__   __| |  ____| |  __ \ 
    | |    | |__) |     /  \        | | | |      | |__    |  \| |    | |    | |__    | |__) |
    | |    |  _  /     / /\ \   _   | | | |      |  __|   | . ` |    | |    |  __|   |  _  / 
    | |    | | \ \    / ____ \ | |__| | | |____  | |____  | |\  |    | |    | |____  | | \ \ 
    |_|    |_|  \_\  /_/    \_\ \____/   \_____| |______| |_| \_|    |_|    |______| |_|  \_\
                                                                            
"""


SPLASH_AUTHORS = "Développé par J. SCHUMAKER & C. RACINET"
SPLASH_HELP = "Entrée : continuer · Q : quitter"


def _lines(mask: str) -> list[str]:
    """Convert a raw ASCII mask to lines without leading/trailing empty lines."""
    return mask.strip("\n").splitlines()


def _normalize_pair(mask_a: str, mask_b: str) -> tuple[list[str], list[str]]:
    """Normalize two masks to the same width and height."""
    lines_a = _lines(mask_a)
    lines_b = _lines(mask_b)

    height = max(len(lines_a), len(lines_b))
    width = max(
        max((len(line) for line in lines_a), default=0),
        max((len(line) for line in lines_b), default=0),
    )

    while len(lines_a) < height:
        lines_a.append("")
    while len(lines_b) < height:
        lines_b.append("")

    lines_a = [line.ljust(width) for line in lines_a]
    lines_b = [line.ljust(width) for line in lines_b]

    return lines_a, lines_b


def render_duotone_logo(
    *,
    violet_mask: str,
    orange_mask: str,
    violet_style: str = "bold #87196B",
    orange_style: str = "bold #F59C00",
) -> Text:
    """Render two superposed ASCII masks as colored Rich text."""
    violet_lines, orange_lines = _normalize_pair(violet_mask, orange_mask)

    text = Text()

    for row_index, (violet_line, orange_line) in enumerate(
        zip(violet_lines, orange_lines, strict=True)
    ):
        for violet_char, orange_char in zip(violet_line, orange_line, strict=True):
            if orange_char != " ":
                text.append(orange_char, style=orange_style)
            elif violet_char != " ":
                text.append(violet_char, style=violet_style)
            else:
                text.append(" ")

        if row_index < len(violet_lines) - 1:
            text.append("\n")

    return text


def render_am_logo() -> Text:
    """Render Arts et Métiers logo."""
    return render_duotone_logo(
        violet_mask=AM_VIOLET,
        orange_mask=AM_ORANGE,
        violet_style="bold #87196B",
        orange_style="bold #F59C00",
    )


def render_lcfc_logo() -> Text:
    """Render LCFC logo."""
    return render_duotone_logo(
        violet_mask=LCFC_VIOLET,
        orange_mask=LCFC_ORANGE,
        violet_style="bold #87196B",
        orange_style="bold #F59C00",
    )
