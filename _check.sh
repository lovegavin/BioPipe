cd ~/biopipe

echo "########## 1. registry build ##########"
python -m biopipe registry build 2>&1 | tail -12

echo
echo "########## 2. peak_nearest_gene_demo ##########"
python scripts/run.py tasks/peak_nearest_gene_demo 2>&1 | tail -15

echo
echo "########## 3. old demos ##########"
for d in tasks/gff3_demo tasks/gff_feature_stats_demo tasks/gene_structure_demo tasks/annotation_gaps_demo tasks/gtf_demo tasks/gtf_annotation_demo; do
  python scripts/run.py "$d" > /dev/null 2>&1 && echo "$d ok" || echo "$d FAILED"
done

echo
echo "########## 4. pytest ##########"
python -m pytest -q \
  tasks/gff_feature_stats_demo \
  tasks/gene_structure_demo \
  tasks/annotation_gaps_demo \
  tasks/peak_nearest_gene_demo \
  2>&1 | tail -5

echo
echo "########## DONE ##########"
