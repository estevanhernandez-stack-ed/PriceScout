import streamlit as st
import datetime

def handle_daypart_click(dp, all_showings, selected_films, selected_theaters):
    """
    Handles clicks on daypart buttons, correctly managing the selection state using a set.
    """
    if 'daypart_selections' not in st.session_state or not isinstance(st.session_state.daypart_selections, set):
        st.session_state.daypart_selections = set()

    selections = st.session_state.daypart_selections
    other_dayparts = {"Matinee", "Twilight", "Prime", "Late Night"}

    if dp == "All":
        if "All" in selections or selections.issuperset(other_dayparts):
            selections.clear()
        else:
            selections.update(other_dayparts)
            selections.add("All")
    else:
        if dp in selections:
            selections.remove(dp)
        else:
            selections.add(dp)

        if selections.issuperset(other_dayparts):
            selections.add("All")
        else:
            selections.discard("All")

    # Now, call the new apply function with the updated state
    apply_daypart_auto_selection(selections, all_showings, selected_films, selected_theaters)


def apply_daypart_auto_selection(daypart_selections, all_showings, films_to_process, theaters_to_process):
    """
    Clears and rebuilds selected_showtimes based on active dayparts.
    - If "All" is selected, it selects ALL showtimes for each film.
    - Otherwise, it selects the EARLIEST showtime for EACH selected daypart for each film.
    """
    st.session_state.selected_showtimes = {}
    if not daypart_selections:
        return

    for theater_name in theaters_to_process:
        for film_title in films_to_process:
            showings_for_film = [s for s in all_showings.get(theater_name, []) if s['film_title'] == film_title]
            if not showings_for_film:
                continue

            # --- LOGIC BRANCH FOR "ALL" vs "INDIVIDUAL" ---
            
            if "All" in daypart_selections:
                # "All" Mode: Select every single showtime for the film.
                for showing in showings_for_film:
                    st.session_state.selected_showtimes.setdefault(theater_name, {}).setdefault(film_title, {}).setdefault(showing['showtime'], []).append(showing)
            
            else:
                # "Individual Daypart" Mode: Select only the first showtime found for each selected daypart.
                sorted_showings = sorted(showings_for_film, key=lambda x: datetime.datetime.strptime(x['showtime'].replace('p', 'PM').replace('a', 'AM'), "%I:%M%p").time())
                
                found_dayparts_for_film = set()
                for showing in sorted_showings:
                    daypart = showing.get('daypart', 'Unknown')
                    # If this showing's daypart is one we want AND we haven't found one for it yet for this film...
                    if daypart in daypart_selections and daypart not in found_dayparts_for_film:
                        # ...select it and mark this daypart as "found" so we don't select another.
                        showings_with_same_time = [s for s in sorted_showings if s['showtime'] == showing['showtime']]
                        st.session_state.selected_showtimes.setdefault(theater_name, {}).setdefault(film_title, {})[showing['showtime']] = showings_with_same_time
                        found_dayparts_for_film.add(daypart)

def render_daypart_selector(all_showings, selected_films, selected_theaters, is_disabled=False, key_prefix=""):
    st.write("Auto-select showtimes by Daypart:")
    daypart_cols = st.columns(5)
    dayparts = ["All", "Matinee", "Twilight", "Prime", "Late Night"]

    for i, dp in enumerate(dayparts):
        is_selected = dp in st.session_state.daypart_selections
        if daypart_cols[i].button(dp, key=f"{key_prefix}_dp_{dp}", type="primary" if is_selected else "secondary", use_container_width=True, disabled=is_disabled):
            handle_daypart_click(dp, all_showings, selected_films, selected_theaters)
            st.rerun()