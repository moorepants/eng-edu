#!/usr/bin/env python

"""
This script processes the data collected from an exam reflection collected via
a Google Form and saved as a CSV file. A PDF is generated containing a summary
of the student's reflection and it is then optionally emailed to the student.

"""

import os
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
import pandas as pd

EMAIL_TEMPLATE = \
"""\
{FirstName},
{poor_text}
I've attached what you wrote for your midterm reflection. You can use this
information to better prepare for the final exam. If you have any questions
while studying please either come visit me or the TA in the coming week or ask
on Piazza. I've also taken into consideration the comments you left for me in
the reflection. I wish you success!

Jason

Jason K. Moore, PhD
Lecturer, Mechanical and Aerospace Engineering Department
University of California, Davis
faculty.engineering.ucdavis.edu/moore
jkm@ucdavis.edu
530-752-4805\
"""

POOR_TEXT = \
"""
Your midterm score was below average and I really want you to bring your grade
up with the final. It will take extra work to do so, but I think you can
significantly improve your grade.
"""

TEMPLATE = \
"""\
===============================================================================
{course_desig} Midterm Reflection
===============================================================================

Student
=======

{FirstName} {LastName}

"""

END_TEMPLATE = \
"""
What percentage of your test-preparation time was spent in each of these activities?
====================================================================================

{test_prep}
Total Percentage: {test_prep_total}

If "other" above please specify.
--------------------------------
{test_prep_other}

Now that you have looked over your graded exam, estimate the percentage of points you lost due to each of the following?
========================================================================================================================

{lost_per}
Total Percentage: {lost_per_total}

If "other" above please specify.
--------------------------------
{lost_per_other}
"""


def generate_pdfs(course, path_to_csv, path_to_directory):
    """Creates a PDF file containing a summary of each student's midterm
    reflection and stores them in the designated directory.

    Parameters
    ==========
    course : string
        A designation for the course, e.g. "EME 150A".
    path_to_csv : string
        The path to a CSV file generated by the Google Form.
    path_to_directory : string
        The path to the directory where the reflection summary PDFs will be
        placed.

    """

    df = pd.read_csv(path_to_csv)

    if not os.path.exists(path_to_directory):
        os.makedirs(path_to_directory)

    for student_idx, col_info in df.iterrows():
        data = {'course_desig': course, 'lost_per': '', 'test_prep': ''}
        rst = TEMPLATE
        data['test_prep_total'] = 0
        data['lost_per_total'] = 0
        for question, answer in zip(df.columns, col_info):
            if question in ['First Name', 'Last Name']:
                data[question.replace(' ', '')] = answer
            elif question.startswith('What percentage'):
                sub_cat = question.split('[')[1][:-1]
                data['test_prep'] += '- ' + sub_cat + ': ' + str(answer) + '\n'
                try:
                    per = float(answer[:-1])
                except:
                    per = 0
                data['test_prep_total'] += per
            elif question.startswith('Now that'):
                sub_cat = question.split('[')[1][:-1]
                data['lost_per'] += '- ' + sub_cat + ': ' + str(answer) + '\n'
                try:
                    per = float(answer[:-1])
                except:
                    per = 0
                data['lost_per_total'] += per
            elif question.startswith('If "other"'):
                if question.endswith('1'):
                    data['lost_per_other'] = str(answer)
                else:
                    data['test_prep_other'] = str(answer)

            elif question.startswith('Unnamed'):
                pass
            else:
                rst += str(question) + '\n' + '=' * len(question)
                rst += '\n' + str(answer) + '\n\n'

        rst += END_TEMPLATE

        rst_file = os.path.join(path_to_directory,
                                data['LastName'].lower() + '.rst')
        tex_file = os.path.join(path_to_directory,
                                data['LastName'].lower() + '.tex')
        with open(rst_file, 'w') as f:
            f.write(rst.format(**data))
        flag = '--latex-preamble="\\usepackage[letterpaper, margin=1in]{geometry}"'
        os.system('rst2latex.py {} "{}" "{}"'.format(flag, rst_file, tex_file))
        os.system('pdflatex -output-directory {} "{}"'.format(path_to_directory,
                                                            tex_file))


    for globule in ["*.aux", "*.log", "*.out", "*.rst", "*.tex"]:
        for f in glob.glob(os.path.join(path_to_directory, globule)):
            print(f)
            os.remove(f)


def send_email(recipient, subject, body, path_to_attachment):
    """Sends an email with text and a single attachment over UC Davis's SMTP
    server.

    Parameters
    ==========
    recipient : string
        The string should contain valid email address for the recipient.
    subject : string
        The subject of the email.
    body : string
        The body text of the email.
    path_to_attachment : string
        The path to a file that should be attached to the email.

    """

    FROM = 'Jason K. Moore <jkm@ucdavis.edu>'
    TO = recipient
    CC = 'jkm@ucdavis.edu'

    msg = MIMEMultipart()
    msg['Subject'] = subject
    msg['From'] = FROM
    msg['To'] = TO
    msg['CC'] = CC

    msg.attach(MIMEText(body))

    part = MIMEBase('application', "octet-stream")
    try:
        part.set_payload(open(path_to_attachment, "rb").read())
    except FileNotFoundError:
        print("{} did not turn in a reflection.".format(TO))
    else:
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="{0}"'.format(
            os.path.basename(path_to_attachment)))
        msg.attach(part)

        try:
            # this may only work (without credentials) when on the campus
            # network
            server = smtplib.SMTP("smtp.ucdavis.edu", 25)
            server.ehlo()
            server.starttls()
            server.sendmail(FROM, [TO, CC], msg.as_string())
            server.quit()  # close?
            print('Successfully sent the mail to: {}'.format(recipient))
        except:
            print("Failed to send mail to {}".format(recipient))


def send_emails(grades_csv, course, directory):
    """Sends the emails to each student.

    Parameters
    ==========
    grades_csv : string
        The path to a CSV file with five columns: "First Name", "Last Name",
        "Email", "Score". The Score column should have their numeric midterm
        grade.
    course : string
        A designation for the course, e.g. "EME 150A".
    directory : string
        The path to the directory that contains the reflection summary PDFs
        that are named by lower case last name.

    """

    df = pd.read_csv(grades_csv)

    average_grade = df['Score'].mean()

    for i, row in df.iterrows():
        if row['Score'] < average_grade:
            poor = POOR_TEXT
        else:
            poor = ''
        vals = {'poor_text': poor, 'FirstName': row['First Name']}
        body = EMAIL_TEMPLATE.format(**vals)
        subject = '{} Midterm Reflection'.format(course)
        pdf = os.path.join(directory, row['Last Name'].lower() + '.pdf')
        send_email(row['Email'], subject,  body, pdf)


if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("course")
    parser.add_argument("csv")
    parser.add_argument('directory')
    parser.add_argument('-e', '--email', help=("This should be a path to the "
                                               "grades csv file, which will "
                                               "be used to send the emails."))
    args = parser.parse_args()

    generate_pdfs(args.course, args.csv, args.directory)

    if args.email:
        send_emails(args.email, args.course, args.directory)
