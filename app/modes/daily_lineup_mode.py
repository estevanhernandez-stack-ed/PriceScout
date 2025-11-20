"""
Daily Lineup Mode - Print-ready theater film schedules
Generates printable daily lineups for individual theaters with blank columns for manual theater numbers.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from app import database


def render_daily_lineup_mode(cache_data, selected_company):
    """
    Main render function for Daily Lineup Mode.
    Allows theater staff to generate print-ready daily film schedules.
    """
    st.title("📋 Daily Lineup - Theater Schedule")
    st.info(
        "Generate a print-ready daily film lineup for your theater. "
        "Perfect for posting schedules or distribution to staff."
    )

    # Get all unique theaters from cache
    all_theaters = []
    if cache_data:
        for market_name, market_data in cache_data.get('markets', {}).items():
            all_theaters.extend(market_data.get('theaters', []))

    theater_names = sorted([t['name'] for t in all_theaters if 'name' in t])

    if not theater_names:
        st.warning("No theaters found in cache. Please build the theater cache first.")
        return

    # Theater selection
    st.subheader("Select Theater")

    # Check if user has a default theater (future feature)
    default_theater_index = 0
    if 'user_default_theater' in st.session_state:
        try:
            default_theater_index = theater_names.index(st.session_state.user_default_theater)
        except ValueError:
            pass

    selected_theater = st.selectbox(
        "Theater",
        options=theater_names,
        index=default_theater_index,
        help="Select the theater to generate a lineup for"
    )

    # Get available dates for selected theater
    available_dates = database.get_dates_for_theater(selected_theater)

    if not available_dates:
        st.warning(f"No showtime data found for {selected_theater}. Please scrape this theater first.")
        return

    # Date selection
    st.subheader("Select Date")

    # Convert string dates to date objects for better UI
    date_options = [datetime.strptime(d, '%Y-%m-%d').date() for d in available_dates]

    # Default to today or the most recent date
    default_date_index = 0
    today = date.today()
    if today in date_options:
        default_date_index = date_options.index(today)

    selected_date_obj = st.selectbox(
        "Date",
        options=date_options,
        index=default_date_index,
        format_func=lambda d: d.strftime('%A, %B %d, %Y'),
        help="Select the date to generate the lineup for"
    )

    selected_date = selected_date_obj.strftime('%Y-%m-%d')

    # Generate button
    st.divider()
    if st.button("📄 Generate Daily Lineup", type="primary", use_container_width=True):
        generate_daily_lineup(selected_theater, selected_date, selected_date_obj)


def generate_daily_lineup(theater_name, date_str, date_obj):
    """Generate and display the daily lineup"""

    # Query showings for this theater and date
    with database._get_db_connection() as conn:
        query = '''
            SELECT
                film_title,
                showtime,
                format,
                daypart
            FROM showings
            WHERE theater_name = ? AND play_date = ?
            ORDER BY film_title, showtime
        '''
        df = pd.read_sql_query(query, conn, params=(theater_name, date_str))

    if df.empty:
        st.warning(f"No showtimes found for {theater_name} on {date_str}")
        return

    # Process the data to group showtimes by film
    lineup_data = []

    for film_title, film_group in df.groupby('film_title', sort=False):
        # Get all showtimes for this film
        showtimes = sorted(film_group['showtime'].tolist())

        # Format showtimes (remove seconds if present)
        formatted_times = [format_showtime(st) for st in showtimes]
        showtimes_str = ', '.join(formatted_times)

        # Get format indicators (3D, IMAX, PLF, etc.)
        formats = film_group['format'].unique()
        format_indicators = get_format_indicators(formats)

        lineup_data.append({
            'Theater #': '',  # Blank column for manual entry
            'Film Title': film_title,
            'Showtimes': showtimes_str,
            'Format': format_indicators
        })

    # Create DataFrame for display
    lineup_df = pd.DataFrame(lineup_data)

    # Display header
    st.success(f"✅ Daily Lineup Generated for {theater_name}")
    st.subheader(f"{date_obj.strftime('%A, %B %d, %Y')}")

    # Display the lineup table
    st.dataframe(
        lineup_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Theater #': st.column_config.TextColumn(
                'Theater #',
                width='small',
                help='Leave blank for manual entry'
            ),
            'Film Title': st.column_config.TextColumn(
                'Film Title',
                width='large'
            ),
            'Showtimes': st.column_config.TextColumn(
                'Showtimes',
                width='large'
            ),
            'Format': st.column_config.TextColumn(
                'Format',
                width='medium',
                help='3D, IMAX, PLF indicators'
            )
        }
    )

    # Print instructions
    st.divider()
    st.info(
        "📌 **Printing Instructions:**\n"
        "1. Use your browser's print function (Ctrl+P or Cmd+P)\n"
        "2. Set orientation to 'Landscape' for best results\n"
        "3. Adjust scale if needed to fit all content on one page\n"
        "4. The 'Theater #' column can be filled in by hand after printing"
    )

    # Download options
    st.subheader("Download Options")
    col1, col2 = st.columns(2)

    with col1:
        # CSV download
        csv_data = lineup_df.to_csv(index=False)
        st.download_button(
            label="📄 Download as CSV",
            data=csv_data,
            file_name=f"daily_lineup_{theater_name}_{date_str}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        # Excel download with enhanced formatting for easy editing
        try:
            from io import BytesIO
            from openpyxl.styles import Font, Alignment, Border, Side, PatternFill

            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                lineup_df.to_excel(writer, index=False, sheet_name='Daily Lineup', startrow=2)

                # Get the workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets['Daily Lineup']

                # Add theater name and date header
                worksheet['A1'] = theater_name
                worksheet['A1'].font = Font(size=14, bold=True)
                worksheet['A2'] = date_obj.strftime('%A, %B %d, %Y')
                worksheet['A2'].font = Font(size=12, bold=True)

                # Format header row (row 3)
                header_fill = PatternFill(start_color='8b0e04', end_color='8b0e04', fill_type='solid')
                header_font = Font(color='FFFFFF', bold=True, size=11)

                for col_num, column in enumerate(lineup_df.columns, 1):
                    cell = worksheet.cell(row=3, column=col_num)
                    cell.fill = header_fill
                    cell.font = header_font
                    cell.alignment = Alignment(horizontal='center', vertical='center')

                # Set column widths for easy editing
                worksheet.column_dimensions['A'].width = 12  # Theater #
                worksheet.column_dimensions['B'].width = 45  # Film Title
                worksheet.column_dimensions['C'].width = 50  # Showtimes
                worksheet.column_dimensions['D'].width = 20  # Format

                # Add borders to all cells with data
                thin_border = Border(
                    left=Side(style='thin'),
                    right=Side(style='thin'),
                    top=Side(style='thin'),
                    bottom=Side(style='thin')
                )

                for row in worksheet.iter_rows(min_row=3, max_row=len(lineup_df) + 3, min_col=1, max_col=4):
                    for cell in row:
                        cell.border = thin_border
                        cell.alignment = Alignment(vertical='top', wrap_text=True)

                # Alternate row colors for easier reading
                light_fill = PatternFill(start_color='F2F2F2', end_color='F2F2F2', fill_type='solid')
                for row_num in range(4, len(lineup_df) + 4, 2):  # Every other row
                    for col_num in range(1, 5):
                        worksheet.cell(row=row_num, column=col_num).fill = light_fill

            excel_data = output.getvalue()

            st.download_button(
                label="📊 Download as Excel (Editable)",
                data=excel_data,
                file_name=f"daily_lineup_{theater_name}_{date_str}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except ImportError:
            st.caption("Excel export requires openpyxl package")

    # Summary statistics
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Films", len(lineup_df))
    with col2:
        total_showtimes = sum(len(row['Showtimes'].split(',')) for _, row in lineup_df.iterrows())
        st.metric("Total Showtimes", total_showtimes)
    with col3:
        # Count premium formats
        premium_count = sum(1 for _, row in lineup_df.iterrows() if row['Format'] and row['Format'] != 'Standard')
        st.metric("Premium Format Shows", premium_count)


def format_showtime(showtime_str):
    """Format showtime string to be more readable"""
    try:
        # Handle different time formats
        if len(showtime_str) == 5:  # HH:MM format
            time_obj = datetime.strptime(showtime_str, '%H:%M')
        elif len(showtime_str) == 8:  # HH:MM:SS format
            time_obj = datetime.strptime(showtime_str, '%H:%M:%S')
        else:
            return showtime_str

        # Convert to 12-hour format with AM/PM
        return time_obj.strftime('%I:%M %p').lstrip('0')
    except:
        return showtime_str


def get_format_indicators(formats):
    """Convert format codes to readable indicators"""
    indicators = []

    for fmt in formats:
        if fmt and fmt.strip() and fmt.upper() != 'STANDARD':
            # Common format mappings
            fmt_upper = fmt.upper()
            if '3D' in fmt_upper:
                indicators.append('3D')
            if 'IMAX' in fmt_upper:
                indicators.append('IMAX')
            if 'UltraScreen'.upper() in fmt_upper or 'ULTRASCREEN' in fmt_upper:
                indicators.append('UltraScreen')
            if 'PLF' in fmt_upper or 'SUPERSCREEN' in fmt_upper:
                indicators.append('PLF')
            if 'DFX' in fmt_upper:
                indicators.append('DFX')
            if 'DOLBY' in fmt_upper:
                indicators.append('Dolby')

            # If no specific format matched but it's not standard, show the original
            if not indicators and fmt_upper != 'STANDARD':
                indicators.append(fmt)

    if not indicators:
        return 'Standard'

    # Remove duplicates and join
    return ', '.join(sorted(set(indicators)))
